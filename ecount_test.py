"""
이카운트 OAPI 연동 테스트 스크립트
실행: python ecount_test.py
"""

from ecount_api import EcountAPI, parse_bulk_result

# ── 인증 정보 설정 ───────────────────────────────
COM_CODE    = "159654"
USER_ID     = "SLOCKIMPLANT"
API_CERT_KEY = "여기에_실인증키_또는_테스트인증키_입력"
# ────────────────────────────────────────────────

api = EcountAPI(com_code=COM_CODE, user_id=USER_ID, api_cert_key=API_CERT_KEY)


def test_zone_and_login():
    print("\n[1] Zone 조회...")
    zone = api.get_zone()
    print(f"    Zone: {zone}")

    print("[2] 로그인...")
    result = api.login(auto_zone=False)
    print(f"    Status: {result.get('Status')}")
    print(f"    SESSION_ID: {api._session_id[:30]}...")
    print("    ✅ 로그인 성공\n")


def test_save_customer():
    print("[3] 거래처 등록 테스트...")
    result = api.save_customer([
        {
            "BUSINESS_NO": "TEST_C001",
            "CUST_NAME": "테스트거래처A",
            "TEL": "02-1234-5678",
            "EMAIL": "test_a@example.com",
        },
        {
            "BUSINESS_NO": "TEST_C002",
            "CUST_NAME": "테스트거래처B",
            "TEL": "02-9999-0000",
        },
    ])

    data = result.get("Data", {})
    print(f"    성공: {data.get('SuccessCnt')}건 / 실패: {data.get('FailCnt')}건")

    for item in parse_bulk_result(result):
        status = "✅" if item["success"] else "❌"
        msg = f"  → {item['error']}" if not item["success"] else ""
        print(f"    {status} [{item['index']}번]{msg}")
    print()


def test_get_product_list():
    print("[4] 품목 목록 조회 테스트...")
    result = api.get_product_list({"PAGE_SIZE": 5, "PAGE_NUM": 1})
    data = result.get("Data", {})
    items = data.get("List", data.get("Datas", []))
    print(f"    조회된 품목 수: {len(items)}건")
    for p in items[:3]:
        print(f"    - {p}")
    print()


if __name__ == "__main__":
    try:
        test_zone_and_login()
        test_save_customer()
        test_get_product_list()
        print("전체 테스트 완료 ✅")
    except Exception as e:
        print(f"\n❌ 오류 발생: {e}")
