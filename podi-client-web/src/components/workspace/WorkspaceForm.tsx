interface WorkspaceFormProps {
  tool?: unknown;
  mode?: string;
}

export default function WorkspaceForm({ tool, mode }: WorkspaceFormProps) {
  return (
    <div className="client-panel">
      <div className="client-panel__header">
        <p className="client-eyebrow">AI 创作</p>
        <h3>输入您的创意</h3>
      </div>

      <div style={{ display: 'grid', gap: '16px' }}>
        <div className="client-field client-field--wide">
          <span>创意描述</span>
          <textarea
            placeholder="请输入您的设计想法或描述..."
            style={{
              width: '100%',
              minHeight: '120px',
              padding: '14px',
              borderRadius: '12px',
              border: '1px solid var(--style3d-border)',
              background: 'var(--style3d-surface-elevated)',
              color: 'var(--style3d-text)',
              resize: 'none',
            }}
          />
        </div>

        <div className="client-upload-box" style={{ marginTop: '8px' }}>
          <div className="client-upload-box__icon">
            <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
              <polyline points="17 8 12 3 7 8" />
              <line x1="12" y1="3" x2="12" y2="15" />
            </svg>
          </div>
          <div>
            <div className="client-upload-box__title">上传参考图片</div>
            <p style={{ margin: 0, fontSize: '13px', color: 'var(--style3d-text-muted)' }}>
              支持 JPG、PNG，最大 10MB
            </p>
          </div>
          <button className="client-primary-button">选择文件</button>
        </div>

        <div className="client-submit-row" style={{ marginTop: '16px' }}>
          <button className="client-primary-button" style={{ flex: 1 }}>
            开始生成
          </button>
          <button className="client-soft-button">
            重置
          </button>
        </div>
      </div>
    </div>
  );
}
