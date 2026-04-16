import { Link } from 'react-router-dom';
import type { ShowcaseCard } from '../../types';

export default function HomeOverview({
  showcaseCards,
}: {
  showcaseCards: ShowcaseCard[];
}) {
  return (
    <section className="client-section">
      <div className="client-section__heading">
        <div>
          <p className="client-eyebrow">核心入口</p>
          <h2>直接从常用入口开始。</h2>
        </div>
      </div>
      <div className="client-home-card-row">
        {showcaseCards.map((item) => (
          <Link key={item.id} className="client-home-card" to={item.path}>
            <div className="client-home-card__media" style={{ backgroundImage: `url(${item.image})` }} />
            <div className="client-home-card__body">
              <strong>{item.title}</strong>
              <span>{item.subtitle}</span>
            </div>
          </Link>
        ))}
      </div>
    </section>
  );
}
