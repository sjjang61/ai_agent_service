import type { AgentStep } from '../../types/agent'

export interface DeployedAppRef {
  /** 그 도구 결과(step)의 id. 같은 배포를 두 번 자동으로 열지 않기 위한 키 */
  stepId: string
  name: string
  url: string
}

/** deploy_web_app 의 성공 결과("Deployed 'name' (…). Open: URL")에서 가장 최근 앱을 꺼낸다. http(s) 주소만 인정한다. */
export function latestDeployedApp(steps: { id: string; type: string; tool?: string; output?: string }[] | undefined): DeployedAppRef | null {
  let found: DeployedAppRef | null = null
  for (const s of steps ?? []) {
    if (s.type !== 'tool_result' || s.tool !== 'deploy_web_app' || typeof s.output !== 'string') continue
    const url = /Open:\s*(https?:\/\/\S+)/.exec(s.output)?.[1]
    if (!url) continue
    found = { stepId: s.id, name: /Deployed '([^']+)'/.exec(s.output)?.[1] ?? '앱', url }
  }
  return found
}

export type { AgentStep }
