export interface DeployedAppRef {
  /** 그 도구 결과(step)의 id. 같은 배포를 두 번 자동으로 열지 않기 위한 키 */
  stepId: string
  name: string
  appId: string
}

/** deploy_web_app 의 성공 결과("Deployed 'name' (…). App ID: UUID")에서 가장 최근 앱을 꺼낸다. */
export function latestDeployedApp(steps: { id: string; type: string; tool?: string; output?: string }[] | undefined): DeployedAppRef | null {
  let found: DeployedAppRef | null = null
  for (const s of steps ?? []) {
    if (s.type !== 'tool_result' || s.tool !== 'deploy_web_app' || typeof s.output !== 'string') continue
    const appId = /App ID:\s*([0-9a-fA-F-]{36})/.exec(s.output)?.[1]
    if (!appId) continue
    found = { stepId: s.id, name: /Deployed '([^']+)'/.exec(s.output)?.[1] ?? '앱', appId }
  }
  return found
}
