import { workspacePreviewExamples } from '../../config/clientContent';

interface WorkspacePreviewProps {
  tool?: unknown;
  mode?: string;
}

export default function WorkspacePreview({ tool, mode }: WorkspacePreviewProps) {
  return (
    <div className="client-panel">
      <div className="client-panel__header--compact">
        <h3>结果预览</h3>
        <span className="client-inline-link">清空</span>
      </div>

      <div
        className="client-result-card__media client-result-card__media--placeholder"
        style={{ minHeight: '300px', borderRadius: '16px', marginBottom: '16px' }}
      >
        <div style={{ textAlign: 'center', padding: '40px' }}>
          <svg
            width="48"
            height="48"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            style={{ opacity: 0.5, margin: '0 auto 16px' }}
          >
            <rect x="3" y="3" width="18" height="18" rx="2" />
            <circle cx="8.5" cy="8.5" r="1.5" />
            <path d="M21 15l-5-5L5 21" />
          </svg>
          <p style={{ color: 'var(--style3d-text-muted)', margin: 0 }}>
            生成的图片将在这里显示
          </p>
        </div>
      </div>

      <div className="client-example-grid">
        {workspacePreviewExamples.map((item) => (
          <div key={item.id} className="client-example-card">
            <div
              className="client-example-card__media"
              style={{
                backgroundImage: `url(${item.image})`,
                backgroundSize: 'cover',
                backgroundPosition: 'center',
              }}
            />
            <div className="client-example-card__body">
              <span>{item.label}</span>
              <strong>{item.title}</strong>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
