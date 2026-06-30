<#
POD_AI generic file-level deployment script.

The online /srv/pod directory is not a Git working tree, so this script packages
changed files from selected local commits, uploads them to Linux, backs up the
original online files, copies the new files, restarts services and records a
deployment history.

Do not commit this file with a real password.
#>

$ErrorActionPreference = "Stop"

# =========================
# Effective config block
# =========================
$SERVER_HOST = "114.55.0.56"
$SERVER_PORT = 22
$SERVER_USER = "root"
$SERVER_PASSWORD = ""
$REMOTE_BASE = "/srv/pod"

$SCRIPT_DIR = if ($PSScriptRoot) {
    $PSScriptRoot
} elseif ($MyInvocation.MyCommand.Path) {
    Split-Path -Parent $MyInvocation.MyCommand.Path
} else {
    (Get-Location).Path
}
if ([string]::IsNullOrWhiteSpace($SCRIPT_DIR)) {
    $SCRIPT_DIR = (Get-Location).Path
}
$LOCAL_REPO = (Resolve-Path (Join-Path $SCRIPT_DIR "..")).Path

# One commit: @("9c32458")
# Multiple commits: @("commit1", "commit2", "commit3")
$COMMITS = @(
    "061618e",
    "a999751",
    "75dece1",
    "84155cf",
    "4303c00",
    "23a5d35",
    "a8d4636",
    "eee2baa",
    "2d3bcf5",
    "febd40d"
)

# Comma-separated fallback: "9c32458" or "commit1,commit2,commit3".
$COMMIT_IDS = "061618e,a999751,75dece1,84155cf,4303c00,23a5d35,a8d4636,eee2baa,2d3bcf5,febd40d"

$RESTART_SERVICES = @("podi-backend.service")
$HEALTH_CHECK_URLS = @("http://127.0.0.1:8099/health")
$RUN_PY_COMPILE = $true
$APPLY_DELETES = $false

$RUN_TIMESTAMP = Get-Date -Format yyyyMMddHHmmss
$LOCAL_LOG_DIR = Join-Path $SCRIPT_DIR "logs"
$LOCAL_LOG_FILE = Join-Path $LOCAL_LOG_DIR "deploy_${RUN_TIMESTAMP}.log"
New-Item -ItemType Directory -Force -Path $LOCAL_LOG_DIR | Out-Null
$TRANSCRIPT_STARTED = $false
try {
    Start-Transcript -Path $LOCAL_LOG_FILE -Append | Out-Null
    $TRANSCRIPT_STARTED = $true
    Write-Host "Local deploy log: $LOCAL_LOG_FILE"
} catch {
    Write-Warning "Start transcript failed: $($_.Exception.Message)"
}

function Require-Command([string]$Name) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if (-not $command) {
        throw "Missing command: $Name"
    }
}

function Resolve-CommandPath([string]$Name, [string[]]$FallbackPaths = @()) {
    $command = Get-Command $Name -ErrorAction SilentlyContinue
    if ($command) {
        return $command.Source
    }
    foreach ($path in $FallbackPaths) {
        if (Test-Path -LiteralPath $path) {
            return $path
        }
    }
    throw "Missing command: $Name"
}

function Assert-LastExit([string]$Label) {
    if ($LASTEXITCODE -ne 0) {
        throw "$Label failed with exit code $LASTEXITCODE."
    }
}

function Quote-Bash([string]$Value) {
    return "'" + $Value.Replace("'", "'\''") + "'"
}

function Is-Blocked-Path([string]$Path) {
    $normalized = $Path.Replace("\", "/")
    if ($normalized -match '(^|/)\.env($|[./])') { return $true }
    if ($normalized -match '(^|/)\.venv($|/)') { return $true }
    if ($normalized -match '(^|/)node_modules($|/)') { return $true }
    if ($normalized -match '(^|/)dist($|/)') { return $true }
    if ($normalized -match '(^|/)__pycache__($|/)') { return $true }
    if ($normalized -match '\.pyc$') { return $true }
    if ($normalized -eq "startup.bat") { return $true }
    return $false
}

function Write-Utf8NoBomLf([string]$Path, [string[]]$Lines) {
    $utf8NoBom = New-Object System.Text.UTF8Encoding($false)
    $content = ""
    if ($Lines.Count -gt 0) {
        $content = ($Lines -join "`n") + "`n"
    }
    [System.IO.File]::WriteAllText($Path, $content, $utf8NoBom)
}

function Test-GitPathExists([string]$RepoRoot, [string]$CommitRef, [string]$Path) {
    & git -C $RepoRoot cat-file -e "${CommitRef}:${Path}" 2>$null
    return $LASTEXITCODE -eq 0
}

Require-Command git

$repoRoot = (Resolve-Path $LOCAL_REPO).Path
$commitList = New-Object System.Collections.Generic.List[string]
foreach ($commit in @($COMMITS)) {
    if (-not [string]::IsNullOrWhiteSpace($commit)) {
        $commitList.Add($commit.Trim())
    }
}
foreach ($commit in ($COMMIT_IDS -split ",")) {
    if (-not [string]::IsNullOrWhiteSpace($commit)) {
        $value = $commit.Trim()
        if (-not $commitList.Contains($value)) {
            $commitList.Add($value)
        }
    }
}
if ($commitList.Count -eq 0) {
    throw "COMMITS or COMMIT_IDS must contain at least one commit id."
}

$deployCommit = $commitList[$commitList.Count - 1]
$commitSha = (& git -C $repoRoot rev-parse --short=12 $deployCommit).Trim()
Assert-LastExit "git rev-parse $deployCommit"
$commitDisplay = ($commitList -join ",")
$target = "${SERVER_USER}@${SERVER_HOST}"
$timestamp = $RUN_TIMESTAMP
$tempRoot = [System.IO.Path]::GetTempPath()
$archivePath = Join-Path $tempRoot "pod_ai_deploy_${commitSha}_${timestamp}.tar"
$manifestPath = Join-Path $tempRoot "pod_ai_deploy_${commitSha}_${timestamp}.manifest"
$deleteManifestPath = Join-Path $tempRoot "pod_ai_deploy_${commitSha}_${timestamp}.delete"
$remoteScriptPath = Join-Path $tempRoot "pod_ai_deploy_${commitSha}_${timestamp}.sh"
$envPath = Join-Path $tempRoot "pod_ai_deploy_${commitSha}_${timestamp}.env"
$remoteArchive = "/tmp/$(Split-Path $archivePath -Leaf)"
$remoteManifest = "/tmp/$(Split-Path $manifestPath -Leaf)"
$remoteDeleteManifest = "/tmp/$(Split-Path $deleteManifestPath -Leaf)"
$remoteScript = "/tmp/$(Split-Path $remoteScriptPath -Leaf)"
$remoteEnv = "/tmp/$(Split-Path $envPath -Leaf)"

$changedPaths = New-Object 'System.Collections.Generic.HashSet[string]'
$deployFiles = New-Object System.Collections.Generic.List[string]
$deleteFiles = New-Object System.Collections.Generic.List[string]

foreach ($commit in $commitList) {
    $nameStatus = & git -C $repoRoot diff-tree --no-commit-id --name-status -r $commit
    Assert-LastExit "git diff-tree $commit"
    if (-not $nameStatus) {
        Write-Host "Commit $commit has no changed files, skip."
        continue
    }
    foreach ($line in $nameStatus) {
        if ([string]::IsNullOrWhiteSpace($line)) { continue }
        $parts = $line -split "`t"
        $status = $parts[0]

        if ($status.StartsWith("R") -or $status.StartsWith("C")) {
            if ($parts.Count -ge 2 -and -not (Is-Blocked-Path $parts[1])) {
                [void]$changedPaths.Add($parts[1])
            }
            if ($parts.Count -ge 3 -and -not (Is-Blocked-Path $parts[2])) {
                [void]$changedPaths.Add($parts[2])
            }
            continue
        }

        if ($parts.Count -ge 2 -and -not (Is-Blocked-Path $parts[1])) {
            [void]$changedPaths.Add($parts[1])
        }
    }
}

foreach ($path in ($changedPaths | Sort-Object)) {
    if (Test-GitPathExists -RepoRoot $repoRoot -CommitRef $deployCommit -Path $path) {
        $deployFiles.Add($path)
    } else {
        $deleteFiles.Add($path)
    }
}

if ($deployFiles.Count -eq 0 -and (-not $APPLY_DELETES -or $deleteFiles.Count -eq 0)) {
    throw "No deployable files found in commits: $commitDisplay."
}

Write-Host "Local repo: $repoRoot"
Write-Host "Deploy commits: $commitDisplay"
Write-Host "Deploy tree commit: $deployCommit ($commitSha)"
Write-Host "Remote target: ${target}:$REMOTE_BASE"
Write-Host "Files to upload:"
$deployFiles | ForEach-Object { Write-Host "  + $_" }
if ($APPLY_DELETES -and $deleteFiles.Count -gt 0) {
    Write-Host "Files to delete:"
    $deleteFiles | ForEach-Object { Write-Host "  - $_" }
}

$remoteScriptContent = @'
#!/usr/bin/env bash
set -euo pipefail

ENV_FILE="${1:?missing env file}"
source "${ENV_FILE}"

RELEASE_DIR="/tmp/pod_ai_release_${COMMIT_SHA}_$(date +%Y%m%d%H%M%S)"
BACKUP_DIR="${REMOTE_BASE}/deploy_backups/local_deploy_${COMMIT_SHA}_$(date +%Y%m%d%H%M%S)"

cleanup() {
  rm -f "${REMOTE_ARCHIVE}" "${REMOTE_MANIFEST}" "${REMOTE_DELETE_MANIFEST}" "${ENV_FILE}" "$0"
}
trap cleanup EXIT

echo "[deploy] remote base: ${REMOTE_BASE}"
test -d "${REMOTE_BASE}"
mkdir -p "${RELEASE_DIR}" "${BACKUP_DIR}"

if [ -s "${REMOTE_ARCHIVE}" ]; then
  tar -xf "${REMOTE_ARCHIVE}" -C "${RELEASE_DIR}"
fi

FILE_COUNT=$(grep -c . "${REMOTE_MANIFEST}" || true)

echo "[deploy] backup changed files -> ${BACKUP_DIR}"
while IFS= read -r file; do
  [ -z "${file}" ] && continue
  case "${file}" in
    /*|*..*) echo "[deploy] unsafe path: ${file}" >&2; exit 2 ;;
  esac
  if [ -e "${REMOTE_BASE}/${file}" ]; then
    mkdir -p "${BACKUP_DIR}/$(dirname "${file}")"
    cp -a "${REMOTE_BASE}/${file}" "${BACKUP_DIR}/${file}"
  fi
done < "${REMOTE_MANIFEST}"

echo "[deploy] copy files"
while IFS= read -r file; do
  [ -z "${file}" ] && continue
  case "${file}" in
    /*|*..*) echo "[deploy] unsafe path: ${file}" >&2; exit 2 ;;
  esac
  mkdir -p "${REMOTE_BASE}/$(dirname "${file}")"
  cp -a "${RELEASE_DIR}/${file}" "${REMOTE_BASE}/${file}"
done < "${REMOTE_MANIFEST}"

if [ "${APPLY_DELETES}" = "1" ]; then
  echo "[deploy] delete files"
  while IFS= read -r file; do
    [ -z "${file}" ] && continue
    case "${file}" in
      /*|*..*) echo "[deploy] unsafe delete path: ${file}" >&2; exit 2 ;;
    esac
    if [ -e "${REMOTE_BASE}/${file}" ]; then
      mkdir -p "${BACKUP_DIR}/deleted/$(dirname "${file}")"
      cp -a "${REMOTE_BASE}/${file}" "${BACKUP_DIR}/deleted/${file}"
      rm -f "${REMOTE_BASE}/${file}"
    fi
  done < "${REMOTE_DELETE_MANIFEST}"
fi

if [ "${RUN_PY_COMPILE}" = "1" ] && [ -x "${REMOTE_BASE}/backend/.venv/bin/python" ]; then
  PY_FILES=""
  while IFS= read -r file; do
    case "${file}" in
      backend/app/*.py|backend/app/*/*.py|backend/app/*/*/*.py) PY_FILES="${PY_FILES} ${file#backend/}" ;;
    esac
  done < "${REMOTE_MANIFEST}"
  if [ -n "${PY_FILES}" ]; then
    echo "[deploy] python compile check"
    cd "${REMOTE_BASE}/backend"
    ./.venv/bin/python -m py_compile ${PY_FILES}
  fi
fi

if [ -n "${RESTART_SERVICES}" ]; then
  for service in ${RESTART_SERVICES}; do
    echo "[deploy] restart ${service}"
    systemctl restart "${service}"
    systemctl status "${service}" --no-pager
  done
fi

if [ -n "${HEALTH_URLS}" ]; then
  for url in ${HEALTH_URLS}; do
    echo "[deploy] health check ${url}"
    HEALTH_OK=0
    # FastAPI 启动时会加载工作流、执行节点和能力种子；线上偶发超过 40 秒，健康检查窗口放宽到 3 分钟。
    for attempt in $(seq 1 60); do
      if curl -fsS "${url}"; then
        echo
        HEALTH_OK=1
        break
      fi
      echo "[deploy] health attempt ${attempt}/60 failed, retry in 3s"
      sleep 3
    done
    if [ "${HEALTH_OK}" != "1" ]; then
      echo "[deploy] health check failed: ${url}" >&2
      mkdir -p "${REMOTE_BASE}/deploy"
      FAILED_AT=$(date '+%Y-%m-%d %H:%M:%S %z')
      printf '%s status=failed stage=health commit_sha=%s commits=%s file_count=%s backup=%s services="%s"\n' "${FAILED_AT}" "${COMMIT_SHA}" "${COMMIT_LIST}" "${FILE_COUNT}" "${BACKUP_DIR}" "${RESTART_SERVICES}" >> "${REMOTE_BASE}/deploy/deploy_history.log"
      if [ -n "${RESTART_SERVICES}" ]; then
        for service in ${RESTART_SERVICES}; do
          echo "[deploy] failed service status ${service}" >&2
          systemctl status "${service}" --no-pager >&2 || true
          echo "[deploy] failed recent logs ${service}" >&2
          journalctl -u "${service}" -n 120 --no-pager >&2 || true
        done
      fi
      exit 7
    fi
  done
fi

mkdir -p "${REMOTE_BASE}/deploy"
DEPLOYED_AT=$(date '+%Y-%m-%d %H:%M:%S %z')
printf '%s commit_sha=%s commits=%s file_count=%s backup=%s services="%s"\n' "${DEPLOYED_AT}" "${COMMIT_SHA}" "${COMMIT_LIST}" "${FILE_COUNT}" "${BACKUP_DIR}" "${RESTART_SERVICES}" >> "${REMOTE_BASE}/deploy/deploy_history.log"
printf '%s\n' "${COMMIT_SHA}" > "${REMOTE_BASE}/DEPLOYED_COMMIT"
cat > "${REMOTE_BASE}/deploy/last_deploy.env" <<EOF
deployed_at=${DEPLOYED_AT}
commit_sha=${COMMIT_SHA}
commits=${COMMIT_LIST}
file_count=${FILE_COUNT}
backup_dir=${BACKUP_DIR}
services=${RESTART_SERVICES}
EOF
echo "[deploy] history: ${REMOTE_BASE}/deploy/deploy_history.log"
echo "[deploy] current: ${REMOTE_BASE}/deploy/last_deploy.env"

if [ -n "${RESTART_SERVICES}" ]; then
  for service in ${RESTART_SERVICES}; do
    echo "[deploy] recent logs ${service}"
    journalctl -u "${service}" -n 80 --no-pager
  done
fi

echo "[deploy] done. backup: ${BACKUP_DIR}"
'@

try {
    foreach ($path in @($archivePath, $manifestPath, $deleteManifestPath, $remoteScriptPath, $envPath)) {
        if (Test-Path $path) { Remove-Item -LiteralPath $path -Force }
    }

    if ($deployFiles.Count -gt 0) {
        & git -C $repoRoot archive --format=tar --output=$archivePath $deployCommit -- $deployFiles
        Assert-LastExit "git archive"
    } else {
        Set-Content -LiteralPath $archivePath -Value "" -NoNewline
    }

    Write-Utf8NoBomLf $manifestPath $deployFiles
    Write-Utf8NoBomLf $deleteManifestPath $deleteFiles
    Write-Utf8NoBomLf $remoteScriptPath @($remoteScriptContent -split "`r?`n")

    $envLines = @(
        "REMOTE_BASE=$(Quote-Bash $REMOTE_BASE)",
        "REMOTE_ARCHIVE=$(Quote-Bash $remoteArchive)",
        "REMOTE_MANIFEST=$(Quote-Bash $remoteManifest)",
        "REMOTE_DELETE_MANIFEST=$(Quote-Bash $remoteDeleteManifest)",
        "COMMIT_SHA=$(Quote-Bash $commitSha)",
        "COMMIT_LIST=$(Quote-Bash $commitDisplay)",
        "APPLY_DELETES=$(if ($APPLY_DELETES) { '1' } else { '0' })",
        "RUN_PY_COMPILE=$(if ($RUN_PY_COMPILE) { '1' } else { '0' })",
        "RESTART_SERVICES=$(Quote-Bash ($RESTART_SERVICES -join ' '))",
        "HEALTH_URLS=$(Quote-Bash ($HEALTH_CHECK_URLS -join ' '))"
    )
    Write-Utf8NoBomLf $envPath $envLines

    $usePuttyPassword = -not [string]::IsNullOrWhiteSpace($SERVER_PASSWORD)
    if ($usePuttyPassword) {
        $pscpCommand = Resolve-CommandPath "pscp" @("C:\Program Files\PuTTY\pscp.exe")
        $plinkCommand = Resolve-CommandPath "plink" @("C:\Program Files\PuTTY\plink.exe")
        $copyArgs = @("-batch", "-P", "$SERVER_PORT", "-pw", $SERVER_PASSWORD)
        $sshArgs = @("-batch", "-P", "$SERVER_PORT", "-pw", $SERVER_PASSWORD)

        Write-Host "Uploading with pscp..."
        & $pscpCommand @copyArgs $archivePath "${target}:$remoteArchive"; Assert-LastExit "upload archive"
        & $pscpCommand @copyArgs $manifestPath "${target}:$remoteManifest"; Assert-LastExit "upload manifest"
        & $pscpCommand @copyArgs $deleteManifestPath "${target}:$remoteDeleteManifest"; Assert-LastExit "upload delete manifest"
        & $pscpCommand @copyArgs $remoteScriptPath "${target}:$remoteScript"; Assert-LastExit "upload remote script"
        & $pscpCommand @copyArgs $envPath "${target}:$remoteEnv"; Assert-LastExit "upload remote env"

        Write-Host "Checking remote bash syntax..."
        & $plinkCommand @sshArgs $target "bash -n $remoteScript"; Assert-LastExit "remote bash syntax check"

        Write-Host "Running remote deploy script..."
        & $plinkCommand @sshArgs $target "bash $remoteScript $remoteEnv"; Assert-LastExit "remote deploy"
    } else {
        Require-Command scp
        Require-Command ssh
        $copyArgs = @("-P", "$SERVER_PORT")
        $sshArgs = @("-p", "$SERVER_PORT")

        Write-Host "Uploading with scp..."
        # 使用一次 scp 传完全部临时文件，避免无 SSH key 时每个文件都要求输入一次密码。
        & scp @copyArgs $archivePath $manifestPath $deleteManifestPath $remoteScriptPath $envPath "${target}:/tmp/"; Assert-LastExit "upload deploy files"

        Write-Host "Checking remote bash syntax, running remote deploy script and verifying deployed commit..."
        # 语法检查、部署和 DEPLOYED_COMMIT 校验放到同一个 ssh 会话里执行，减少交互式密码输入次数。
        # 远端必须写入本次 commit，否则本地脚本直接失败，避免出现“窗口显示成功但线上仍是旧版本”的误判。
        $verifyCommand = "bash -n $remoteScript && bash $remoteScript $remoteEnv && test `"`$(cat $REMOTE_BASE/DEPLOYED_COMMIT 2>/dev/null)`" = '$commitSha' && echo '[deploy] verified DEPLOYED_COMMIT=$commitSha'"
        & ssh @sshArgs $target $verifyCommand; Assert-LastExit "remote deploy"
    }
}
finally {
    foreach ($path in @($archivePath, $manifestPath, $deleteManifestPath, $remoteScriptPath, $envPath)) {
        if (Test-Path $path) {
            Remove-Item -LiteralPath $path -Force
        }
    }
    if ($TRANSCRIPT_STARTED) {
        Stop-Transcript | Out-Null
        Write-Host "Local deploy log saved: $LOCAL_LOG_FILE"
    }
}
