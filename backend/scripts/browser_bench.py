#!/usr/bin/env python
"""브라우저 자동화 측정: 검증된 사이트 시나리오를 반복 실행해 통과율·실패 원인·시간·토큰을 기록하고 보여 준다.

사용 (backend 폴더에서, 서버와 같은 .env·DB 로 실행. 데스크톱 앱 브라우저를 쓰려면 앱이 켜져 있어야 한다):
  python scripts/browser_bench.py cases                         # 측정 대상 목록
  python scripts/browser_bench.py run --label baseline          # 모든 대상을 3회씩 (사이트 수 × 3 × 약 1~2분)
  python scripts/browser_bench.py run --label t1 --attempts 1 --sites 다나와,에누리
  python scripts/browser_bench.py report --label baseline
  python scripts/browser_bench.py compare baseline after-heal
실행은 읽기 전용(결제 직전·상태 변경 제외)이고, 메일 분야는 실제 메일함을 읽으므로 --include-mail 이 있어야 포함된다.
"""
import argparse
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


def pct(x):
    return "-" if x is None else f"{round(x * 100)}%"


def print_report(agg: dict, title: str) -> None:
    print(f"\n== {title} ==")
    if not agg["runs"]:
        print("결과가 없습니다")
        return
    if agg.get("excluded_infra"):
        print(f"※ 실행 환경 오류(모델 연결 등)로 브라우저를 못 쓴 {agg['excluded_infra']}회는 통과율에서 제외했습니다")
    print(f"실행 {agg['runs']}회 · 통과 {agg['passed']} ({pct(agg['pass_rate'])}) · 평균 {agg['avg_seconds']}초 · 평균 {agg['avg_steps']}동작 · 평균 토큰 {agg['avg_tokens'] or '미집계'} · 자동 복구 {agg['heals']}회")
    print(f"동작 오류율 {pct(agg['action_error_rate'])} · 불안정한 사이트(통과·실패가 섞임): {', '.join(agg['flaky_sites']) or '없음'}")
    if agg["errors"]:
        print("동작 오류 분류: " + " / ".join(f"{k} {v}" for k, v in agg["errors"].items()))
    if agg["fail_reasons"]:
        print("통과 못한 이유: " + " / ".join(f"{k} {v}" for k, v in list(agg["fail_reasons"].items())[:8]))
    print(f"\n{'사이트':<14}{'통과율':>7}{'실행':>5}{'초':>7}{'동작':>7}{'토큰':>9}  주요 오류·실패 이유")
    for s in agg["sites"]:
        notes = list(s["fail_reasons"].items())[:2] + list(s["errors"].items())[:2]
        print(f"{s['site']:<14}{pct(s['pass_rate']):>7}{s['runs']:>5}{s['avg_seconds'] or '-':>7}{s['avg_steps'] or '-':>7}{s['avg_tokens'] or '-':>9}  " + ("; ".join(f"{k} {v}" for k, v in notes) + ("  ⚠ 불안정" if s["flaky"] else "")))


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)
    for name in ("cases", "run"):
        p = sub.add_parser(name)
        p.add_argument("--sites", default="", help="쉼표로 구분한 사이트 이름 (비우면 모두)")
        p.add_argument("--verticals", default="", help="쉼표로 구분한 분야 키 (예: shopping,flight)")
        p.add_argument("--include-mail", action="store_true", help="메일 분야 포함 (실제 메일함을 읽는다)")
        if name == "run":
            p.add_argument("--label", required=True, help="측정 묶음 이름 (예: baseline)")
            p.add_argument("--attempts", type=int, default=3)
            p.add_argument("--user-id", default="", help="실행할 사용자 id (기본: LOCAL_BROWSER_USER_ID)")
    r = sub.add_parser("report"); r.add_argument("--label", default="", help="비우면 가장 최근 묶음")
    c = sub.add_parser("compare"); c.add_argument("a"); c.add_argument("b")
    sub.add_parser("labels")
    args = ap.parse_args()

    from sqlalchemy import select
    from app.config import settings
    from app.db.session import AsyncSessionLocal, engine
    from app.models.site_profile import SiteProfile
    from app.services import browser_bench as bb
    from app.services import site_profile_service as svc
    from app.agent import site_tips

    try:
        if args.cmd in ("cases", "run"):
            async with AsyncSessionLocal() as db:
                await svc.refresh(db)
                sites = (await db.execute(select(SiteProfile))).scalars().all()
            vspecs = {v.key: v.spec for v in site_tips.all_verticals()}
            cases = bb.build_cases(sites, vspecs, {x.strip() for x in args.sites.split(",") if x.strip()} or None,
                                   {x.strip() for x in args.verticals.split(",") if x.strip()} or None, args.include_mail)
            if args.cmd == "cases":
                for c_ in cases:
                    print(f"{c_['name']:<14} {c_['vertical'] or '-':<10} {c_['start_url']}  입력: {c_['inputs']}")
                print(f"\n{len(cases)}개 대상")
                return
            uid = args.user_id or settings.LOCAL_BROWSER_USER_ID
            if not uid:
                sys.exit("LOCAL_BROWSER_USER_ID 가 없어 실행할 사용자를 정할 수 없습니다 (--user-id)")
            if not cases:
                sys.exit("측정 대상이 없습니다")
            print(f"{len(cases)}개 대상 × {args.attempts}회 = {len(cases) * args.attempts}번 실행 (label={args.label})")
            try:
                n = await bb.run_batch(uid, cases, args.label, args.attempts, progress=lambda m: print(m, flush=True))
            except RuntimeError as e:
                sys.exit(f"\n중단: {e}")
            async with AsyncSessionLocal() as db:
                print_report(bb.aggregate(await bb.load_results(db, args.label)), f"{args.label} (이번 {n}회 저장)")
        elif args.cmd == "labels":
            async with AsyncSessionLocal() as db:
                for x in await bb.list_labels(db):
                    print(f"{x['label']:<24} {x['runs']:>4}회 · 통과율 {pct(x['pass_rate'])} · 마지막 {x['last']}")
        elif args.cmd == "report":
            async with AsyncSessionLocal() as db:
                label = args.label or ((await bb.list_labels(db)) or [{"label": ""}])[0]["label"]
                print_report(bb.aggregate(await bb.load_results(db, label)), label or "(없음)")
        elif args.cmd == "compare":
            async with AsyncSessionLocal() as db:
                a, b = bb.aggregate(await bb.load_results(db, args.a)), bb.aggregate(await bb.load_results(db, args.b))
            print(f"\n전체: {args.a} {pct(a['pass_rate'])} ({a['runs']}회) → {args.b} {pct(b['pass_rate'])} ({b['runs']}회)")
            print(f"동작 오류율: {pct(a['action_error_rate'])} → {pct(b['action_error_rate'])} · 평균 시간 {a['avg_seconds']}초 → {b['avg_seconds']}초 · 평균 동작 {a['avg_steps']} → {b['avg_steps']}")
            print(f"\n{'사이트':<14}{args.a[:10]:>12}{args.b[:10]:>12}{'변화':>8}{'초(전→후)':>14}")
            for row in bb.compare(a, b):
                d = "-" if row["delta"] is None else f"{row['delta'] * 100:+.0f}%p"
                print(f"{row['site']:<14}{pct(row['pass_a']):>12}{pct(row['pass_b']):>12}{d:>8}{str(row['sec_a'] or '-') + ' → ' + str(row['sec_b'] or '-'):>14}")
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
