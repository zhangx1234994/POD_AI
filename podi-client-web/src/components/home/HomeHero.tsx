import { useEffect, useMemo, useState } from 'react';
import { ArrowRightIcon } from 'tdesign-icons-react';
import { Link } from 'react-router-dom';
import type { AssetItem } from '../../types';

export default function HomeHero({
  balance,
  isAuthenticated,
  previewAssets,
}: {
  balance: number | null;
  isAuthenticated: boolean;
  previewAssets: AssetItem[];
}) {
  const slides = useMemo(
    () => [
      {
        id: 'design',
        label: '数据驱动设计',
        title: '把设计、商拍、图像处理和积分体系，收进同一个工作室。',
        description: '让灵感、参考图、结果图和任务状态都停留在一个前台，不再来回切换后台页面。',
        image: previewAssets[0]?.image,
      },
      {
        id: 'pattern',
        label: '图案工作流',
        title: '从图案提取，到四方连续，再到最终放大，一条线做完。',
        description: '把印花处理做成真正可回来的工作流，而不是一次性工具调用。',
        image: previewAssets[1]?.image || previewAssets[0]?.image,
      },
      {
        id: 'commerce',
        label: '电商营销素材',
        title: '围绕一张主图，继续裂变套图、细节图和短视频。',
        description: '让业务侧拿到的不只是单张图，而是一组能直接落地使用的内容资产。',
        image: previewAssets[2]?.image || previewAssets[0]?.image,
      },
    ],
    [previewAssets],
  );
  const [activeIndex, setActiveIndex] = useState(0);

  useEffect(() => {
    const timer = window.setInterval(() => {
      setActiveIndex((prev) => (prev + 1) % slides.length);
    }, 5000);
    return () => window.clearInterval(timer);
  }, [slides.length]);

  const activeSlide = slides[activeIndex];

  return (
    <section className="client-hero client-hero--clean">
      <div className="client-hero__content client-hero__content--single">
        <div
          className="client-hero__stage"
          style={activeSlide.image ? { backgroundImage: `linear-gradient(135deg, rgba(18,18,18,0.24), rgba(18,18,18,0.06)), url(${activeSlide.image})` } : undefined}
        >
          <div className="client-hero__stage-copy">
            <p className="client-eyebrow">PODI 工作室</p>
            <span className="client-hero__stage-tag">{activeSlide.label}</span>
            <h1>{activeSlide.title}</h1>
            <p>{activeSlide.description}</p>
            <div className="client-hero__actions">
              <Link className="client-primary-link" to="/design/text-to-style">
                立即探索 <ArrowRightIcon size="16" />
              </Link>
            </div>
          </div>
          <div className="client-hero__stage-dots">
            {slides.map((slide, index) => (
              <button
                key={slide.id}
                type="button"
                className={`client-hero__stage-dot${index === activeIndex ? ' is-active' : ''}`}
                onClick={() => setActiveIndex(index)}
                aria-label={`切换到第 ${index + 1} 张`}
              >
                {String(index + 1).padStart(2, '0')}
              </button>
            ))}
          </div>
        </div>
        <div className="client-hero__filmstrip">
          {slides.map((slide, index) => (
            <button
              key={slide.id}
              type="button"
              className={`client-hero__film-card${index === activeIndex ? ' is-active' : ''}`}
              onClick={() => setActiveIndex(index)}
            >
              <div className="client-hero__film-media" style={slide.image ? { backgroundImage: `url(${slide.image})` } : undefined} />
              <div className="client-hero__film-body">
                <span>{slide.label}</span>
                <strong>{slide.title}</strong>
              </div>
            </button>
          ))}
        </div>
      </div>
    </section>
  );
}
