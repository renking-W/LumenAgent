<template>
  <section class="about-page">
    <header class="author-intro">
      <div class="author-intro__copy">
        <p class="author-eyebrow">ABOUT THE BUILDER</p>
        <h2 class="author-name">
          王业成
          <span>Agent Developer</span>
        </h2>
        <p class="author-lead">
          2027 届软件工程本科生，专注 Agent 应用、Java 后端与测试开发。
          从运行时、工具扩展到业务接入，把模型能力做成可以持续运行的工程系统。
        </p>
        <div class="author-actions" aria-label="作者联系方式">
          <a
            class="author-action author-action--primary"
            href="https://github.com/renking-W"
            target="_blank"
            rel="noopener noreferrer"
          >
            <Github :size="17" aria-hidden="true" />
            GitHub
            <ExternalLink :size="14" aria-hidden="true" />
          </a>
          <a
            class="author-action"
            href="https://blog.csdn.net/renking666"
            target="_blank"
            rel="noopener noreferrer"
          >
            <BookOpenText :size="17" aria-hidden="true" />
            技术博客
          </a>
          <a class="author-action" href="mailto:3194676188@qq.com">
            <Mail :size="17" aria-hidden="true" />
            联系作者
          </a>
        </div>
      </div>

      <aside class="runtime-signature" aria-label="Agent Runtime 工程轨迹">
        <div class="runtime-signature__head">
          <img src="/logo.svg" alt="LumenAgent" />
          <div>
            <strong>lumen.agent / author</strong>
            <span>runtime trace</span>
          </div>
          <i aria-hidden="true"></i>
        </div>
        <ol class="runtime-trace">
          <li>
            <span>01</span>
            <strong>THINK</strong>
            <small>拆解问题与上下文</small>
          </li>
          <li>
            <span>02</span>
            <strong>CALL</strong>
            <small>连接工具与真实业务</small>
          </li>
          <li>
            <span>03</span>
            <strong>OBSERVE</strong>
            <small>验证结果与运行状态</small>
          </li>
          <li>
            <span>04</span>
            <strong>REFINE</strong>
            <small>持续迭代系统能力</small>
          </li>
        </ol>
      </aside>
    </header>

    <div class="author-facts" aria-label="作者概览">
      <div>
        <span>方向</span>
        <strong>Agent 工程</strong>
      </div>
      <div>
        <span>主力语言</span>
        <strong>Java / Python</strong>
      </div>
      <div>
        <span>毕业年份</span>
        <strong>2027</strong>
      </div>
      <div>
        <span>当前项目</span>
        <strong>LumenAgent</strong>
      </div>
    </div>

    <section class="author-section author-story">
      <div class="section-heading">
        <span>BUILDING PHILOSOPHY</span>
        <h3>让 Agent 真正进入业务链路</h3>
      </div>
      <div class="author-story__body">
        <p>
          我关注的不只是模型能否回答问题，而是 Agent 如何拥有稳定的工具循环、可控的上下文、
          可恢复的会话状态，以及与现有业务系统清晰的集成边界。
        </p>
        <p>
          LumenAgent 是这套思路的完整实践：从异步 Function Calling、MCP、RAG 和 Memory，
          到审批、定时任务、远程虚拟机与 API 接入，逐步形成一个可独立部署的 Agent Runtime。
        </p>
      </div>
    </section>

    <section class="author-section">
      <div class="section-heading">
        <span>SELECTED WORK</span>
        <h3>核心经历</h3>
      </div>
      <div class="experience-timeline">
        <article>
          <time>2026.05 - 至今</time>
          <div>
            <h4>LumenAgent <span>核心开发</span></h4>
            <p>
              从 0 到 1 构建通用 Agent Runtime，覆盖 Agent Loop、模型适配、MCP、知识库、记忆、
              SKILL、工具审批、定时任务及远程虚拟机操作。
            </p>
          </div>
        </article>
        <article>
          <time>2025.09 - 至今</time>
          <div>
            <h4>上海耶噗网络科技有限公司 <span>测试开发工程师</span></h4>
            <p>
              独立落地效能评估 Agent 与测试用例生成 Agent，开发代码分析、需求拆分 MCP 工具，
              并参与精准化测试平台后端建设。
            </p>
          </div>
        </article>
        <article>
          <time>2025.12</time>
          <div>
            <h4>XMall 智能商城 <span>Java 后端 / Agent 集成</span></h4>
            <p>
              将 LumenAgent 作为独立服务接入 Java 商城，通过 SSE 派发模型、工具和异常事件，
              为订单查询、商品推荐等场景提供 Agent 能力。
            </p>
          </div>
        </article>
        <article>
          <time>2025.07 - 2025.08</time>
          <div>
            <h4>上海游族网络科技有限公司 <span>游戏测试工程师</span></h4>
            <p>
              参与 WebGL、Android、Unity 多端功能、接口与性能验证，完成测试设计、缺陷跟踪和自动化实践。
            </p>
          </div>
        </article>
      </div>
    </section>

    <section class="author-section">
      <div class="section-heading">
        <span>ENGINEERING TOOLKIT</span>
        <h3>技术能力</h3>
      </div>
      <div class="capability-grid">
        <article>
          <Code2 :size="20" aria-hidden="true" />
          <h4>Agent Engineering</h4>
          <p>Agent Loop / Function Calling / MCP / RAG / Embedding / Memory / SKILL</p>
        </article>
        <article>
          <Blocks :size="20" aria-hidden="true" />
          <h4>Backend Systems</h4>
          <p>Java / Spring Boot / FastAPI / asyncio / MySQL / Redis / RabbitMQ</p>
        </article>
        <article>
          <ScanSearch :size="20" aria-hidden="true" />
          <h4>Quality Engineering</h4>
          <p>接口测试 / 性能测试 / 自动化测试 / 精准化测试 / Agent 效果评测</p>
        </article>
      </div>
    </section>

    <footer class="author-footer">
      <div>
        <span>EDUCATION & HONORS</span>
        <strong>莆田学院 · 软件工程</strong>
        <p>蓝桥杯国家级三等奖 · 天梯赛国家级三等奖 · CET-4</p>
      </div>
      <a
        href="https://github.com/renking-W/LumenAgent"
        target="_blank"
        rel="noopener noreferrer"
      >
        <Github :size="18" aria-hidden="true" />
        查看 LumenAgent 源码
        <ExternalLink :size="15" aria-hidden="true" />
      </a>
    </footer>
  </section>
</template>

<script setup lang="ts">
import {
  Blocks,
  BookOpenText,
  Code2,
  ExternalLink,
  Github,
  Mail,
  ScanSearch,
} from 'lucide-vue-next'
</script>

<style scoped>
.about-page {
  width: min(1180px, 100%);
  margin: 0 auto;
  padding: 48px 48px 64px;
  color: var(--color-navy-800);
}

.author-intro {
  display: grid;
  grid-template-columns: minmax(0, 1.25fr) minmax(360px, 0.75fr);
  gap: 56px;
  align-items: center;
  min-height: 390px;
}

.author-eyebrow,
.section-heading > span,
.author-footer > div > span {
  margin: 0 0 12px;
  color: #6B8C5C;
  font-family: var(--font-mono);
  font-size: 0.72rem;
  font-weight: 700;
  letter-spacing: 0;
}

.author-name {
  margin: 0;
  color: #2C4A28;
  font-family: var(--font-display);
  font-size: 3rem;
  line-height: 1.06;
  letter-spacing: 0;
}

.author-name span {
  display: block;
  margin-top: 10px;
  color: var(--color-navy-500);
  font-family: var(--font-mono);
  font-size: 0.9rem;
  font-weight: 600;
  letter-spacing: 0;
}

.author-lead {
  max-width: 680px;
  margin: 28px 0 0;
  color: var(--color-navy-600);
  font-size: 1.03rem;
  line-height: 1.9;
}

.author-actions {
  display: flex;
  flex-wrap: wrap;
  gap: 10px;
  margin-top: 30px;
}

.author-action {
  min-height: 40px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 14px;
  border: 1px solid var(--color-slate-200);
  border-radius: 6px;
  color: var(--color-navy-700);
  background: var(--color-white);
  font-size: 0.84rem;
  font-weight: 600;
  text-decoration: none;
}

.author-action:hover {
  border-color: #8AAC7A;
  color: #2C4A28;
  text-decoration: none;
  transform: translateY(-1px);
}

.author-action--primary {
  border-color: #2C4A28;
  color: var(--color-white);
  background: #2C4A28;
}

.author-action--primary:hover {
  border-color: #1F371D;
  color: var(--color-white);
  background: #1F371D;
}

.runtime-signature {
  overflow: hidden;
  border: 1px solid #D5E3CC;
  border-radius: 8px;
  background: #F7FAF4;
  box-shadow: var(--shadow-md);
}

.runtime-signature__head {
  min-height: 72px;
  display: grid;
  grid-template-columns: 40px 1fr 10px;
  gap: 12px;
  align-items: center;
  padding: 14px 18px;
  border-bottom: 1px solid #D5E3CC;
  background: #EEF5E6;
}

.runtime-signature__head img {
  width: 40px;
  height: 40px;
}

.runtime-signature__head strong,
.runtime-signature__head span {
  display: block;
  font-family: var(--font-mono);
}

.runtime-signature__head strong {
  color: #2C4A28;
  font-size: 0.8rem;
}

.runtime-signature__head span {
  margin-top: 4px;
  color: #6B8C5C;
  font-size: 0.68rem;
}

.runtime-signature__head i {
  width: 8px;
  height: 8px;
  border-radius: 50%;
  background: var(--color-success);
  box-shadow: 0 0 0 4px rgba(16, 185, 129, 0.12);
}

.runtime-trace {
  list-style: none;
  margin: 0;
  padding: 12px 18px 18px;
}

.runtime-trace li {
  position: relative;
  min-height: 58px;
  display: grid;
  grid-template-columns: 34px 82px 1fr;
  align-items: center;
  gap: 10px;
  border-bottom: 1px solid #E1E9DC;
  font-family: var(--font-mono);
}

.runtime-trace li:last-child {
  border-bottom: none;
}

.runtime-trace li > span {
  color: #A07D00;
  font-size: 0.68rem;
}

.runtime-trace li > strong {
  color: #2C4A28;
  font-size: 0.78rem;
}

.runtime-trace li > small {
  color: var(--color-navy-500);
  font-family: var(--font-sans);
  font-size: 0.76rem;
}

.author-facts {
  display: grid;
  grid-template-columns: repeat(4, minmax(0, 1fr));
  margin: 12px 0 0;
  border-top: 1px solid var(--color-slate-200);
  border-bottom: 1px solid var(--color-slate-200);
}

.author-facts > div {
  min-height: 92px;
  display: flex;
  flex-direction: column;
  justify-content: center;
  gap: 8px;
  padding: 16px 22px;
  border-right: 1px solid var(--color-slate-200);
}

.author-facts > div:last-child {
  border-right: none;
}

.author-facts span {
  color: var(--color-navy-500);
  font-size: 0.75rem;
}

.author-facts strong {
  color: var(--color-navy-800);
  font-family: var(--font-mono);
  font-size: 0.9rem;
}

.author-section {
  display: grid;
  grid-template-columns: 240px minmax(0, 1fr);
  gap: 48px;
  padding: 64px 0;
  border-bottom: 1px solid var(--color-slate-200);
}

.section-heading h3 {
  margin: 0;
  color: #2C4A28;
  font-size: 1.45rem;
  line-height: 1.35;
  letter-spacing: 0;
}

.author-story__body {
  display: grid;
  grid-template-columns: repeat(2, minmax(0, 1fr));
  gap: 32px;
}

.author-story__body p {
  margin: 0;
  color: var(--color-navy-600);
  line-height: 1.95;
}

.experience-timeline {
  border-top: 1px solid var(--color-slate-300);
}

.experience-timeline article {
  display: grid;
  grid-template-columns: 150px minmax(0, 1fr);
  gap: 24px;
  padding: 24px 0;
  border-bottom: 1px solid var(--color-slate-200);
}

.experience-timeline article:last-child {
  border-bottom: none;
}

.experience-timeline time {
  color: #6B8C5C;
  font-family: var(--font-mono);
  font-size: 0.75rem;
  line-height: 1.7;
}

.experience-timeline h4 {
  margin: 0;
  color: var(--color-navy-800);
  font-size: 0.98rem;
  letter-spacing: 0;
}

.experience-timeline h4 span {
  margin-left: 8px;
  color: var(--color-navy-500);
  font-size: 0.78rem;
  font-weight: 500;
}

.experience-timeline p {
  margin: 10px 0 0;
  color: var(--color-navy-600);
  font-size: 0.88rem;
  line-height: 1.8;
}

.capability-grid {
  display: grid;
  grid-template-columns: repeat(3, minmax(0, 1fr));
  gap: 26px;
}

.capability-grid article {
  padding-top: 18px;
  border-top: 3px solid #D5E3CC;
}

.capability-grid svg {
  color: #A07D00;
}

.capability-grid h4 {
  margin: 16px 0 10px;
  color: #2C4A28;
  font-family: var(--font-mono);
  font-size: 0.86rem;
  letter-spacing: 0;
}

.capability-grid p {
  margin: 0;
  color: var(--color-navy-600);
  font-size: 0.82rem;
  line-height: 1.8;
}

.author-footer {
  display: flex;
  align-items: flex-end;
  justify-content: space-between;
  gap: 32px;
  padding: 48px 0 0;
}

.author-footer strong {
  display: block;
  color: #2C4A28;
  font-size: 1rem;
}

.author-footer p {
  margin: 8px 0 0;
  color: var(--color-navy-500);
  font-size: 0.82rem;
}

.author-footer > a {
  min-height: 42px;
  display: inline-flex;
  align-items: center;
  gap: 8px;
  padding: 0 16px;
  border: 1px solid #2C4A28;
  border-radius: 6px;
  color: #2C4A28;
  font-size: 0.84rem;
  font-weight: 700;
  text-decoration: none;
}

.author-footer > a:hover {
  color: var(--color-white);
  background: #2C4A28;
  text-decoration: none;
}

@media (max-width: 960px) {
  .about-page {
    padding: 36px 28px 52px;
  }

  .author-intro {
    grid-template-columns: 1fr;
    gap: 36px;
  }

  .runtime-signature {
    width: 100%;
  }

  .author-section {
    grid-template-columns: 1fr;
    gap: 28px;
  }
}

@media (max-width: 640px) {
  .about-page {
    padding: 28px 18px 40px;
  }

  .author-name {
    font-size: 2.25rem;
  }

  .author-actions {
    display: grid;
    grid-template-columns: 1fr;
  }

  .author-action {
    justify-content: center;
  }

  .runtime-trace li {
    grid-template-columns: 28px 70px 1fr;
    gap: 8px;
  }

  .author-facts {
    grid-template-columns: repeat(2, minmax(0, 1fr));
  }

  .author-facts > div:nth-child(2) {
    border-right: none;
  }

  .author-facts > div:nth-child(-n + 2) {
    border-bottom: 1px solid var(--color-slate-200);
  }

  .author-story__body,
  .capability-grid {
    grid-template-columns: 1fr;
  }

  .experience-timeline article {
    grid-template-columns: 1fr;
    gap: 8px;
  }

  .experience-timeline h4 span {
    display: block;
    margin: 5px 0 0;
  }

  .author-footer {
    align-items: stretch;
    flex-direction: column;
  }

  .author-footer > a {
    justify-content: center;
  }
}

@media (prefers-reduced-motion: reduce) {
  .author-action {
    transition: none;
  }
}
</style>
