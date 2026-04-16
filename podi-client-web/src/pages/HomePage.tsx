import { useEffect } from 'react';
import { Link } from 'react-router-dom';
import { roleCases } from '../config/clientCatalog';
import './HomePage.css';
import { homeHeroSignals, homeLayerCards } from '../config/clientContent';
import { commercialSignals, funnelMetrics, landingScenarios, launchWorkflows, productNorthStar, templateLibrary } from '../config/clientProduct';
import { clientVisualRegistry } from '../config/clientVisuals';
import { trackClientEvent } from '../services/clientAnalytics';
import { buildTemplateLocationState } from '../services/workspaceSeeds';

export default function HomePage() {
  useEffect(() => {
    trackClientEvent('client_page_view', { page: 'home' });
  }, []);

  return (
    <div className="client-home">
      <section className="client-home__hero">
        <div className="client-home__hero-copy">
          <span className="client-home__eyebrow">Industry SaaS For Fashion Teams</span>
          <h1>{productNorthStar.title}</h1>
          <p>{productNorthStar.subtitle}</p>
          <div className="client-home__hero-actions">
            <Link className="client-home__primary" to={productNorthStar.primaryCta.path}>
              {productNorthStar.primaryCta.label}
            </Link>
            <Link
              className="client-home__secondary"
              to={productNorthStar.secondaryCta.path}
              onClick={() => trackClientEvent('home_secondary_cta_click', { path: productNorthStar.secondaryCta.path })}
            >
              {productNorthStar.secondaryCta.label}
            </Link>
          </div>
          <div className="client-home__hero-helper">{productNorthStar.helper}</div>
          <div className="client-home__hero-summary">
            {homeHeroSignals.map((signal) => (
              <article key={signal.label} className="client-home__hero-summary-card">
                <span>{signal.label}</span>
                <strong>{signal.title}</strong>
              </article>
            ))}
          </div>
        </div>
        <div className="client-home__hero-visual" style={{ backgroundImage: `url(${clientVisualRegistry.homeHero.url})` }}>
          <div className="client-home__hero-visual-label">
            <span>Home / Conversion Front</span>
            <strong>案例、试用、工作路径必须在第一屏就成立。</strong>
          </div>
          <div className="client-home__hero-orbit client-accent--sky">
            <span>获客</span>
            <strong>案例 + 试用</strong>
          </div>
          <div className="client-home__hero-orbit client-accent--amber">
            <span>激活</span>
            <strong>首任务成功</strong>
          </div>
          <div className="client-home__hero-orbit client-accent--emerald">
            <span>留存</span>
            <strong>结果继续创作</strong>
          </div>
          <div className="client-home__hero-orbit client-accent--rose">
            <span>变现</span>
            <strong>余额与套餐升级</strong>
          </div>
        </div>
      </section>

      <section className="client-home__metrics">
        {funnelMetrics.map((metric) => (
          <article key={metric.label} className="client-home__metric-card">
            <span>{metric.label}</span>
            <strong>{metric.value}</strong>
            <p>{metric.note}</p>
          </article>
        ))}
      </section>

      <section className="client-home__layers">
        <div className="client-home__section-heading">
          <span>终局结构</span>
          <h2>客户端最终要同时扛住转化、生产和经营三层职责。</h2>
        </div>
        <div className="client-home__layer-grid">
          {homeLayerCards.map((item) => (
            <article key={item.label} className="client-home__layer-card">
              <span>{item.label}</span>
              <strong>{item.title}</strong>
              <p>{item.note}</p>
            </article>
          ))}
        </div>
      </section>

      <section className="client-home__scenarios">
        <div className="client-home__section-heading">
          <span>行业路径</span>
          <h2>不是卖功能，而是卖一条能跑通的业务路径。</h2>
        </div>
        <div className="client-home__scenario-grid">
          {landingScenarios.map((scenario) => (
            <article key={scenario.id} className="client-home__scenario-card">
              <div className="client-home__scenario-media" style={{ backgroundImage: `url(${scenario.image})` }} />
              <div className="client-home__scenario-body">
                <span>{scenario.label}</span>
                <strong>{scenario.title}</strong>
                <p>{scenario.summary}</p>
                <em>{scenario.outcome}</em>
                <Link to={scenario.path} onClick={() => trackClientEvent('home_scenario_click', { scenarioId: scenario.id, path: scenario.path })}>
                  进入这条路径
                </Link>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="client-home__workflow">
        <div className="client-home__section-heading">
          <span>首发高频工作流</span>
          <h2>第一阶段只做高频、稳定、能形成复用的动作。</h2>
        </div>
        <div className="client-home__workflow-grid">
          {launchWorkflows.map((workflow) => (
            <Link
              key={workflow.id}
              to={workflow.path}
              className={`client-home__workflow-card client-accent--${workflow.accent}`}
              onClick={() => trackClientEvent('home_workflow_click', { workflowId: workflow.id, path: workflow.path })}
            >
              <div>
                <span>{workflow.category.toUpperCase()}</span>
                <strong>{workflow.title}</strong>
              </div>
              <p>{workflow.subtitle}</p>
              <em>{workflow.note}</em>
            </Link>
          ))}
        </div>
      </section>

      <section className="client-home__cases">
        <div className="client-home__section-heading">
          <span>案例资产</span>
          <h2>案例不是装饰，而是首任务发起率和二次使用率的发动机。</h2>
        </div>
        <div className="client-home__case-grid">
          {roleCases.slice(0, 3).map((item) => (
            <article key={item.id} className={`client-home__case-card client-accent--${item.accent}`}>
              <div className="client-home__case-media" style={{ backgroundImage: `url(${item.image})` }} />
              <div className="client-home__case-body">
                <span>{item.role}</span>
                <strong>{item.headline}</strong>
                <div className="client-home__case-stats">
                  <div>
                    <small>效率提升</small>
                    <b>{item.uplift}</b>
                  </div>
                  <div>
                    <small>时间节约</small>
                    <b>{item.savings}</b>
                  </div>
                </div>
              </div>
            </article>
          ))}
        </div>
      </section>

      <section className="client-home__templates">
        <div className="client-home__section-heading">
          <span>模板资产</span>
          <h2>每个高频入口都要有模板、案例和下一步推荐，避免用户面对空白表单。</h2>
        </div>
        <div className="client-home__template-grid">
          {templateLibrary.map((template) => (
            <article key={template.id} className="client-home__template-card">
              <span>{template.category.toUpperCase()}</span>
              <strong>{template.title}</strong>
              <p>{template.summary}</p>
              <blockquote>{template.prompt}</blockquote>
              <Link
                to={template.path}
                state={buildTemplateLocationState(template)}
                onClick={() => trackClientEvent('template_start_click', { source: 'home', templateId: template.id, path: template.path })}
              >
                用这条模板开始
              </Link>
            </article>
          ))}
        </div>
      </section>

      <section className="client-home__commercial">
        <div className="client-home__section-heading">
          <span>商业前台</span>
          <h2>余额、套餐和升级不是附属页，而是前台连续使用的必要组成部分。</h2>
        </div>
        <div className="client-home__commercial-grid">
          {commercialSignals.map((item) => (
            <article key={item.title} className="client-home__commercial-card">
              <strong>{item.title}</strong>
              <p>{item.note}</p>
            </article>
          ))}
        </div>
        <div className="client-home__final-cta">
          <div>
            <span>Phase 1 交付目标</span>
            <strong>让新用户在一次会话里完成首任务、回看结果、沉淀资产，并看见清晰的下一步付费路径。</strong>
          </div>
          <Link to="/studio" onClick={() => trackClientEvent('home_final_cta_click', { path: '/studio' })}>
            进入工作室开始
          </Link>
        </div>
      </section>
    </div>
  );
}
