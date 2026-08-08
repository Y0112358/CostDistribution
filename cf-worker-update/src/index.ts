export interface Env {
  GH_TOKEN: string
  OWNER: string
  REPO: string
  WORKFLOW: string
}

export default {
  async fetch(req: Request, env: Env): Promise<Response> {
    const url = new URL(req.url)
    if (req.method === 'POST' && url.pathname === '/update') {
      const res = await fetch(
        `https://api.github.com/repos/${env.OWNER}/${env.REPO}/actions/workflows/${env.WORKFLOW}/dispatches`,
        {
          method: 'POST',
          headers: {
            Authorization: `Bearer ${env.GH_TOKEN}`,
            Accept: 'application/vnd.github+json',
            'Content-Type': 'application/json',
            'User-Agent': 'theme-rotation-update',
          },
          body: JSON.stringify({ ref: 'main' }),
        },
      )
      const body = res.ok
        ? JSON.stringify({ ok: true })
        : JSON.stringify({ ok: false, status: res.status, detail: res.statusText })
      return new Response(body, {
        status: res.ok ? 200 : res.status,
        headers: { 'Content-Type': 'application/json' },
      })
    }
    return new Response(JSON.stringify({ error: 'POST /update' }), {
      status: 404,
      headers: { 'Content-Type': 'application/json' },
    })
  },
}
