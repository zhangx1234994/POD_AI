import { useEffect, useMemo, useState } from 'react';
import { abilityApi } from '@/services/abilityApi';
import type {
  AbilityInfo,
  AbilityInvokeResponse,
  AbilitySchemaField,
} from '@/types/ability';
import { Button } from '@/components/ui/button';
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from '@/components/ui/card';
import { Input } from '@/components/ui/input';
import { Textarea } from '@/components/ui/textarea';
import { Switch } from '@/components/ui/switch';
import { Label } from '@/components/ui/label';
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from '@/components/ui/select';
import { Badge } from '@/components/ui/badge';
import { toast } from 'sonner';
import { Loader2, RefreshCw, Search, Upload, X, Image as ImageIcon } from 'lucide-react';
import clsx from 'clsx';

type SchemaValueMap = Record<string, string | number | boolean>;

type UploadPreview = {
  name: string;
  preview: string;
  base64: string;
};

const abilityCategories: Record<string, string> = {
  image_generation: '图片生成',
  image_process: '图片处理',
  text_generation: '文本生成',
  video_generation: '视频生成',
  other: '其他',
};

const providerLabelMap: Record<string, string> = {
  baidu: '百度智能云',
  volcengine: '火山引擎',
  comfyui: 'ComfyUI',
  kie: 'KIE 市场',
};

const fieldSupportsArray = (name: string) => {
  const lowered = name.toLowerCase();
  return (
    lowered.endsWith('_urls') ||
    lowered.endsWith('_list') ||
    lowered.endsWith('_inputs') ||
    lowered === 'image_urls' ||
    lowered === 'input_urls'
  );
};

const convertOption = (option: any): { label: string; value: string } => {
  if (typeof option === 'string') {
    return { label: option, value: option };
  }
  if (option && typeof option === 'object') {
    return {
      label: String(option.label ?? option.value ?? ''),
      value: String(option.value ?? option.label ?? ''),
    };
  }
  return { label: String(option ?? ''), value: String(option ?? '') };
};

const ensureStringArray = (input: string): string[] =>
  input
    .split(/\r?\n/)
    .map((line) => line.trim())
    .filter(Boolean);

const formatJson = (value?: Record<string, unknown> | null) =>
  value ? JSON.stringify(value, null, 2) : '';

const fileToBase64 = (file: File): Promise<string> =>
  new Promise((resolve, reject) => {
    const reader = new FileReader();
    reader.onload = () => {
      const result = reader.result?.toString() ?? '';
      const [, base64] = result.split(',');
      resolve(base64 || result);
    };
    reader.onerror = () => reject(reader.error);
    reader.readAsDataURL(file);
  });

export function AbilityLabPage() {
  const [abilities, setAbilities] = useState<AbilityInfo[]>([]);
  const [loadingList, setLoadingList] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const [selectedAbilityId, setSelectedAbilityId] = useState<string | null>(null);
  const [schemaValues, setSchemaValues] = useState<SchemaValueMap>({});
  const [imageUrlInput, setImageUrlInput] = useState('');
  const [uploads, setUploads] = useState<UploadPreview[]>([]);
  const [invokeResult, setInvokeResult] = useState<AbilityInvokeResponse | null>(null);
  const [invoking, setInvoking] = useState(false);
  const [search, setSearch] = useState('');

  useEffect(() => {
    void loadAbilities();
  }, []);

  useEffect(() => {
    if (abilities.length > 0 && !selectedAbilityId) {
      setSelectedAbilityId(abilities[0]?.id ?? null);
    }
  }, [abilities, selectedAbilityId]);

  const selectedAbility = useMemo(
    () => abilities.find((item) => item.id === selectedAbilityId) || null,
    [abilities, selectedAbilityId]
  );

  const schemaFields: AbilitySchemaField[] = useMemo(() => {
    const fields = selectedAbility?.inputSchema?.fields;
    if (!fields || !Array.isArray(fields)) return [];
    return fields;
  }, [selectedAbility?.id]);

  useEffect(() => {
    if (!selectedAbility) {
      setSchemaValues({});
      setImageUrlInput('');
      setUploads([]);
      setInvokeResult(null);
      return;
    }
    const defaults = selectedAbility.defaultParams || {};
    const nextValues: SchemaValueMap = {};
    schemaFields.forEach((field) => {
      const fallback =
        (defaults?.[field.name] as string | number | boolean | undefined) ??
        (field.defaultValue as string | number | boolean | undefined) ??
        (field.default as string | number | boolean | undefined);
      if (fallback !== undefined) {
        nextValues[field.name] = fallback;
      }
      if (field.name === 'image_url' && typeof fallback === 'string') {
        setImageUrlInput(fallback);
      }
    });
    setSchemaValues(nextValues);
    setInvokeResult(null);
    setUploads([]);
  }, [selectedAbility?.id, schemaFields]);

  const filteredAbilities = useMemo(() => {
    const q = search.trim().toLowerCase();
    if (!q) return abilities;
    return abilities.filter((ability) => {
      const label = `${ability.displayName} ${ability.capabilityKey} ${ability.provider}`;
      return label.toLowerCase().includes(q);
    });
  }, [abilities, search]);

  const loadAbilities = async () => {
    try {
      setLoadingList(true);
      const items = await abilityApi.listAbilities();
      setAbilities(items);
    } catch (error) {
      console.error(error);
      toast.error('加载能力列表失败，请稍后重试');
    } finally {
      setLoadingList(false);
    }
  };

  const refreshAbilities = async () => {
    try {
      setRefreshing(true);
      const items = await abilityApi.listAbilities();
      setAbilities(items);
      toast.success('能力列表已刷新');
    } catch (error) {
      toast.error('刷新失败，请稍后再试');
    } finally {
      setRefreshing(false);
    }
  };

  const handleFieldChange = (name: string, value: string | number | boolean) => {
    setSchemaValues((prev) => ({
      ...prev,
      [name]: value,
    }));
    if (name === 'image_url' && typeof value === 'string') {
      setImageUrlInput(value);
    }
  };

  const handleImageUpload = async (files: FileList | null) => {
    if (!files || files.length === 0) return;
    const arr = Array.from(files).slice(0, 3);
    try {
      const previews: UploadPreview[] = [];
      for (const file of arr) {
        const base64 = await fileToBase64(file);
        const previewUrl = URL.createObjectURL(file);
        previews.push({
          name: file.name,
          base64,
          preview: previewUrl,
        });
      }
      setUploads(previews);
    } catch (error) {
      console.error('convert image error', error);
      toast.error('图片读取失败，请重试');
    }
  };

  const removeUpload = (name: string) => {
    setUploads((prev) => prev.filter((item) => item.name !== name));
  };

  const buildInputsPayload = (): Record<string, unknown> => {
    const payload: Record<string, unknown> = {};
    schemaFields.forEach((field) => {
      const value = schemaValues[field.name];
      if (field.type === 'switch') {
        payload[field.name] = Boolean(value);
        return;
      }
      if (value === '' || value === undefined || value === null) return;
      if (field.type === 'number') {
        const parsed = Number(value);
        if (!Number.isNaN(parsed)) {
          payload[field.name] = parsed;
        }
        return;
      }
      if (fieldSupportsArray(field.name) && typeof value === 'string') {
        payload[field.name] = ensureStringArray(value);
        return;
      }
      payload[field.name] = value;
    });
    return payload;
  };

  const handleInvoke = async () => {
    if (!selectedAbility) return;
    const inputs = buildInputsPayload();
    const requiresImage = Boolean(
      selectedAbility.requiresImage ||
        selectedAbility.metadata?.requires_image_input
    );
    const primaryImageBase64 = uploads[0]?.base64;
    if (
      requiresImage &&
      !primaryImageBase64 &&
      !imageUrlInput &&
      !(inputs.image_url || inputs.imageUrl)
    ) {
      toast.error('该能力需要图片，请上传或填写 URL');
      return;
    }
    setInvoking(true);
    setInvokeResult(null);
    try {
      const payload = {
        inputs,
        imageUrl: imageUrlInput || undefined,
        imageBase64: primaryImageBase64,
        images: uploads.length
          ? uploads.map((item) => ({
              name: item.name,
              base64: item.base64,
            }))
          : undefined,
      };
      const response = await abilityApi.invokeAbility(selectedAbility.id, payload);
      setInvokeResult(response);
      toast.success('已完成调用');
    } catch (error: any) {
      const message = error?.friendlyMessage || error?.message || '调用失败，请检查参数';
      toast.error(message);
    } finally {
      setInvoking(false);
    }
  };

  const renderField = (field: AbilitySchemaField) => {
    const value = schemaValues[field.name];
    const commonProps = {
      id: field.name,
      name: field.name,
    };
    switch (field.type) {
      case 'textarea':
        return (
          <Textarea
            {...commonProps}
            value={(value as string) ?? ''}
            placeholder={field.placeholder}
            rows={4}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
          />
        );
      case 'select': {
        const options = (field.options || []).map(convertOption);
        return (
          <Select
            value={(value as string) ?? options[0]?.value ?? ''}
            onValueChange={(val) => handleFieldChange(field.name, val)}
          >
            <SelectTrigger>
              <SelectValue placeholder="请选择" />
            </SelectTrigger>
            <SelectContent>
              {options.map((opt) => (
                <SelectItem key={opt.value} value={opt.value}>
                  {opt.label}
                </SelectItem>
              ))}
            </SelectContent>
          </Select>
        );
      }
      case 'number':
        return (
          <Input
            {...commonProps}
            type="number"
            value={value ?? ''}
            placeholder={field.placeholder}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
          />
        );
      case 'switch':
        return (
          <div className="flex items-center gap-2">
            <Switch
              checked={Boolean(value)}
              onCheckedChange={(checked) => handleFieldChange(field.name, checked)}
              id={field.name}
            />
            <Label htmlFor={field.name}>{Boolean(value) ? '开启' : '关闭'}</Label>
          </div>
        );
      case 'text':
      default:
        return (
          <Input
            {...commonProps}
            value={(value as string) ?? ''}
            placeholder={field.placeholder}
            onChange={(e) => handleFieldChange(field.name, e.target.value)}
          />
        );
    }
  };

  const renderOutputAssets = (assets?: AbilityInvokeResponse['images']) => {
    if (!assets || assets.length === 0) return null;
    return (
      <div className="grid md:grid-cols-2 gap-4">
        {assets.map((asset, index) => {
          const previewSrc =
            asset.base64 && asset.base64.length > 100
              ? `data:image/png;base64,${asset.base64}`
              : asset.ossUrl || asset.sourceUrl || '';
          if (!previewSrc) {
            return (
              <Card key={`asset-${index}`}>
                <CardContent className="py-4 text-sm text-muted-foreground">
                  暂无可预览图片，原始链接：{' '}
                  {(asset.ossUrl || asset.sourceUrl || '') || '未知'}
                </CardContent>
              </Card>
            );
          }
          return (
            <Card key={`asset-${index}`}>
              <CardHeader className="pb-2">
                <CardTitle className="text-sm font-medium">
                  输出 {index + 1}
                </CardTitle>
              </CardHeader>
              <CardContent>
                <img
                  src={previewSrc}
                  alt={`ability-output-${index}`}
                  className="w-full rounded-lg border object-cover"
                />
                {asset.ossUrl && (
                  <a
                    href={asset.ossUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-primary underline mt-2 inline-block"
                  >
                    OSS 地址
                  </a>
                )}
                {!asset.ossUrl && asset.sourceUrl && (
                  <a
                    href={asset.sourceUrl}
                    target="_blank"
                    rel="noreferrer"
                    className="text-xs text-primary underline mt-2 inline-block"
                  >
                    厂商原始链接
                  </a>
                )}
              </CardContent>
            </Card>
          );
        })}
      </div>
    );
  };

  return (
    <div className="p-4 md:p-6 space-y-6">
      <div className="flex flex-col md:flex-row md:items-center md:justify-between gap-4">
        <div>
          <h1 className="text-xl font-semibold">能力实验室</h1>
          <p className="text-sm text-muted-foreground">
            直接调用统一能力接口，支持图片增强、ComfyUI 工作流、KIE 市场等多种能力
          </p>
        </div>
        <Button variant="outline" onClick={refreshAbilities} disabled={refreshing || loadingList}>
          {refreshing ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <RefreshCw className="w-4 h-4 mr-2" />}
          刷新列表
        </Button>
      </div>

      <div className="flex flex-col gap-6 lg:flex-row">
        <aside className="lg:w-80 space-y-4">
          <div className="relative">
            <Search className="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-muted-foreground" />
            <Input
              placeholder="搜索能力、厂商或关键字"
              className="pl-9"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
            />
          </div>
          <div className="border rounded-xl p-2 max-h-[540px] overflow-auto bg-card">
            {loadingList ? (
              <div className="flex items-center justify-center py-10 text-muted-foreground">
                <Loader2 className="w-5 h-5 animate-spin mr-2" />
                正在加载能力...
              </div>
            ) : filteredAbilities.length === 0 ? (
              <p className="text-sm text-muted-foreground text-center py-6">暂无匹配能力</p>
            ) : (
              filteredAbilities.map((ability) => (
                <button
                  key={ability.id}
                  onClick={() => setSelectedAbilityId(ability.id)}
                  className={clsx(
                    'w-full text-left px-3 py-2 rounded-lg border mb-2 last:mb-0 hover:border-primary transition',
                    selectedAbilityId === ability.id ? 'border-primary bg-primary/5' : 'border-transparent'
                  )}
                >
                  <div className="flex items-center justify-between">
                    <p className="font-medium text-sm">{ability.displayName}</p>
                    <Badge variant="outline" className="text-xs">
                      {providerLabelMap[ability.provider] || ability.provider}
                    </Badge>
                  </div>
                  <p className="text-xs text-muted-foreground mt-1">
                    {ability.capabilityKey} · {abilityCategories[ability.category] || ability.category}
                  </p>
                </button>
              ))
            )}
          </div>
        </aside>

        <section className="flex-1 space-y-6">
          {!selectedAbility ? (
            <Card className="p-6 text-center text-muted-foreground">
              请选择左侧的能力以查看详情和调用参数
            </Card>
          ) : (
            <>
              <Card>
                <CardHeader>
                  <CardTitle className="flex items-center justify-between gap-2 flex-wrap">
                    <span>{selectedAbility.displayName}</span>
                    <div className="flex items-center gap-2">
                      <Badge variant="secondary">
                        {providerLabelMap[selectedAbility.provider] || selectedAbility.provider}
                      </Badge>
                      <Badge>{selectedAbility.capabilityKey}</Badge>
                    </div>
                  </CardTitle>
                  <CardDescription>
                    {selectedAbility.description || '暂无描述'}
                  </CardDescription>
                </CardHeader>
                <CardContent className="space-y-4 text-sm">
                  <div className="flex flex-wrap gap-2 text-muted-foreground">
                    <Badge variant="outline">
                      分类：{abilityCategories[selectedAbility.category] || selectedAbility.category}
                    </Badge>
                    {selectedAbility.requiresImage && <Badge variant="outline">需要图片输入</Badge>}
                    {selectedAbility.supportsMultipleImages && <Badge variant="outline">支持多图输出</Badge>}
                    {selectedAbility.maxOutputImages && (
                      <Badge variant="outline">最高 {selectedAbility.maxOutputImages} 张图</Badge>
                    )}
                  </div>
                  {selectedAbility.metadata && (
                    <details className="text-xs text-muted-foreground">
                      <summary className="cursor-pointer">展开元数据</summary>
                      <pre className="mt-2 rounded-lg bg-muted/40 p-3 overflow-auto max-h-48">
                        {formatJson(selectedAbility.metadata)}
                      </pre>
                    </details>
                  )}
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>输入参数</CardTitle>
                  <CardDescription>根据需要填写真正调用时的参数，可直接使用默认值</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {schemaFields.length === 0 && (
                    <p className="text-sm text-muted-foreground">
                      该能力尚未配置可视化表单，请直接在 JSON 输入框中传递参数。
                    </p>
                  )}
                  <div className="grid gap-4">
                    {schemaFields.map((field) => (
                      <div key={field.name} className="space-y-2">
                        <div className="flex items-center justify-between">
                          <Label htmlFor={field.name}>{field.label || field.name}</Label>
                          {field.required && (
                            <span className="text-xs text-destructive">必填</span>
                          )}
                        </div>
                        {renderField(field)}
                        {field.description && (
                          <p className="text-xs text-muted-foreground whitespace-pre-line">{field.description}</p>
                        )}
                      </div>
                    ))}
                  </div>

                  <div className="space-y-2">
                    <Label>图片 URL（可选）</Label>
                    <Input
                      value={imageUrlInput}
                      placeholder="https://example.com/image.png"
                      onChange={(e) => setImageUrlInput(e.target.value)}
                    />
                    <p className="text-xs text-muted-foreground">
                      若填写 OSS / HTTP 链接，将优先使用该地址。需要多图时可在上方字段中填写 image_urls 或上传多张图片。
                    </p>
                  </div>

                  <div className="space-y-2">
                    <Label>上传图片（支持多张）</Label>
                    <div className="border rounded-lg p-4 space-y-4">
                      <label className="flex flex-col items-center justify-center border border-dashed rounded-lg px-6 py-6 cursor-pointer hover:border-primary transition text-sm text-muted-foreground">
                        <Upload className="w-5 h-5 mb-2" />
                        选择文件
                        <input
                          type="file"
                          accept="image/*"
                          multiple
                          onChange={(e) => handleImageUpload(e.target.files)}
                          className="hidden"
                        />
                      </label>
                      {uploads.length > 0 && (
                        <div className="grid grid-cols-2 md:grid-cols-3 gap-3">
                          {uploads.map((item) => (
                            <div key={item.name} className="relative border rounded-lg overflow-hidden">
                              <img src={item.preview} alt={item.name} className="w-full h-32 object-cover" />
                              <button
                                type="button"
                                onClick={() => removeUpload(item.name)}
                                className="absolute top-1 right-1 bg-background/80 rounded-full p-1"
                              >
                                <X className="w-3 h-3" />
                              </button>
                              <p className="text-xs truncate px-2 py-1 bg-background/80">{item.name}</p>
                            </div>
                          ))}
                        </div>
                      )}
                    </div>
                  </div>

                  <Button
                    className="w-full"
                    size="lg"
                    onClick={handleInvoke}
                    disabled={invoking}
                  >
                    {invoking ? <Loader2 className="w-4 h-4 mr-2 animate-spin" /> : <ImageIcon className="w-4 h-4 mr-2" />}
                    {invoking ? '调用中…' : '立即调用能力'}
                  </Button>
                </CardContent>
              </Card>

              <Card>
                <CardHeader>
                  <CardTitle>返回结果</CardTitle>
                  <CardDescription>实时展示能力返回的图片、文本或原始 JSON</CardDescription>
                </CardHeader>
                <CardContent className="space-y-4">
                  {!invokeResult ? (
                    <p className="text-sm text-muted-foreground">
                      调用成功后将在此展示输出内容。
                    </p>
                  ) : (
                    <>
                      <div className="text-xs text-muted-foreground space-y-1">
                        <div>
                          请求 ID：<span className="font-mono text-foreground">{invokeResult.requestId}</span>
                        </div>
                        {invokeResult.logId !== undefined && invokeResult.logId !== null && (
                          <div>
                            Log ID：<span className="font-mono text-foreground">{invokeResult.logId}</span>
                          </div>
                        )}
                        {typeof invokeResult.durationMs === 'number' && (
                          <div>耗时：{invokeResult.durationMs} ms</div>
                        )}
                      </div>
                      {renderOutputAssets(invokeResult.images)}
                      {invokeResult.texts && invokeResult.texts.length > 0 && (
                        <div className="space-y-2">
                          <Label>文本/描述</Label>
                          <div className="rounded-lg border bg-muted/40 p-3 text-sm whitespace-pre-wrap">
                            {invokeResult.texts.join('\n')}
                          </div>
                        </div>
                      )}
                      {invokeResult.assets && invokeResult.assets.length > 0 && (
                        <div className="space-y-2">
                          <Label>附件/OSS 链接</Label>
                          <ul className="text-sm space-y-1">
                            {invokeResult.assets.map((asset, index) => (
                              <li key={`asset-link-${index}`}>
                                <a
                                  href={asset.ossUrl || asset.sourceUrl || '#'}
                                  target="_blank"
                                  rel="noreferrer"
                                  className="text-primary underline"
                                >
                                  {asset.tag || `附件-${index + 1}`}
                                </a>
                              </li>
                            ))}
                          </ul>
                        </div>
                      )}
                      <details className="text-xs text-muted-foreground">
                        <summary className="cursor-pointer">原始响应</summary>
                        <pre className="mt-2 rounded-lg bg-muted/40 p-3 overflow-auto max-h-64">
                          {formatJson(invokeResult.raw ?? invokeResult.metadata ?? null)}
                        </pre>
                      </details>
                    </>
                  )}
                </CardContent>
              </Card>
            </>
          )}
        </section>
      </div>
    </div>
  );
}

export default AbilityLabPage;
