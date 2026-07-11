/**
 * 图片上传组件 — 拖拽/点击上传
 */
import { useCallback, useRef, useState } from "react";
import { Upload, CheckCircle2 } from "lucide-react";

interface Props {
  onFilesSelected: (files: File[]) => void;
  accept?: string;
  hint?: string;
  compact?: boolean;
}

export default function ImageUploader({
  onFilesSelected,
  accept = "image/jpeg,image/png,image/webp",
  hint = "支持 JPG、PNG、WebP",
  compact = false,
}: Props) {
  const [dragOver, setDragOver] = useState(false);
  const [previewFiles, setPreviewFiles] = useState<File[]>([]);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    (fileList: FileList | null) => {
      if (!fileList) return;
      const files = Array.from(fileList).filter((f) =>
        f.type.startsWith("image/")
      );
      if (files.length === 0) return;
      setPreviewFiles(files.slice(0, 8));
      onFilesSelected(files);
    },
    [onFilesSelected]
  );

  return (
    <div
      className={`image-uploader ${compact ? "compact" : ""} ${previewFiles.length > 0 ? "has-files" : ""} ${dragOver ? "drag-over" : ""}`}
      onDragOver={(e) => {
        e.preventDefault();
        setDragOver(true);
      }}
      onDragLeave={() => setDragOver(false)}
      onDrop={(e) => {
        e.preventDefault();
        setDragOver(false);
        handleFiles(e.dataTransfer.files);
      }}
      onClick={() => inputRef.current?.click()}
      role="button"
      tabIndex={0}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") inputRef.current?.click();
      }}
    >
      <input
        ref={inputRef}
        type="file"
        multiple
        accept={accept}
        style={{ display: "none" }}
        onChange={(e) => handleFiles(e.target.files)}
      />

      {previewFiles.length > 0 ? (
        <div className="uploader-preview">
          <div className="uploader-thumbs">
            {previewFiles.slice(0, 6).map((f, i) => (
              <img
                key={i}
                src={URL.createObjectURL(f)}
                alt={f.name}
              />
            ))}
            {previewFiles.length > 6 && (
              <div className="more-thumb">+{previewFiles.length - 6}</div>
            )}
          </div>
          <div className="uploader-summary">
            <CheckCircle2 size={16} />
            <span>已选择 {previewFiles.length} 张图片</span>
          </div>
          <p className="uploader-hint">点击或拖拽可重新选择</p>
        </div>
      ) : (
        <div className="uploader-empty">
          <Upload size={compact ? 24 : 32} />
          <h3>{compact ? "点击上传图片" : "拖拽图片到这里"}</h3>
          <p>{hint}</p>
        </div>
      )}
    </div>
  );
}
