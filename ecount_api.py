"""
이카운트 OAPI V2 클라이언트

URL 구조:
  Zone 조회: https://oapi.ecount.com/OAPI/V2/Zone
  로그인:     https://oapi{ZONE}.ecount.com/OAPI/V2/OAPILogin
  이후 호출:  https://oapi{ZONE}.ecount.com/OAPI/V2/{Path}?SESSION_ID={SESSION_ID}

사용 예시:
    from ecount_api import EcountAPI

    api = EcountAPI(com_code="159654", user_id="SLOCKIMPLANT", api_cert_key="YOUR_CERT_KEY")
    api.login()

    # 품목 목록 조회
    result = api.get_product_list()

    # 판매 등록
    api.save_sale(...)
"""

import requests
from datetime import datetime
from typing import Optional


class EcountAPIError(Exception):
    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"[{code}] {message}")


class EcountAPI:
    ZONE_URL = "https://oapi.ecount.com/OAPI/V2/Zone"

    def __init__(
        self,
        com_code: str,
        user_id: str,
        api_cert_key: str,
        lan_type: str = "ko-KR",
        zone: str = "",
    ):
        self.com_code = com_code
        self.user_id = user_id
        self.api_cert_key = api_cert_key
        self.lan_type = lan_type

        self._zone: str = zone          # e.g. "AC"
        self._session_id: Optional[str] = None
        self._session = requests.Session()
        self._session.headers.update({"Content-Type": "application/json"})

    # ──────────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────────

    @property
    def _base_url(self) -> str:
        return f"https://oapi{self._zone}.ecount.com/OAPI/V2"

    def _url(self, path: str) -> str:
        return f"{self._base_url}/{path}?SESSION_ID={self._session_id}"

    def _post(self, path: str, payload: dict) -> dict:
        if not self._session_id:
            raise EcountAPIError("NOT_LOGGED_IN", "login()을 먼저 호출하세요.")
        resp = self._session.post(self._url(path), json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        self._raise_on_error(result)
        return result

    @staticmethod
    def _raise_on_error(result: dict):
        status = str(result.get("Status", "200"))
        if status != "200":
            data = result.get("Data", {})
            code = data.get("Code", status) if isinstance(data, dict) else status
            msg = data.get("Msg", "오류") if isinstance(data, dict) else str(data)
            raise EcountAPIError(code, msg)

    # ──────────────────────────────────────────────
    # Zone 조회
    # ──────────────────────────────────────────────

    def get_zone(self) -> str:
        """회사코드로 Zone 조회 후 내부에 저장하고 반환."""
        resp = self._session.post(
            self.ZONE_URL,
            json={"COM_CODE": self.com_code},
            timeout=30,
        )
        resp.raise_for_status()
        result = resp.json()
        self._raise_on_error(result)
        zone = result.get("Data", {}).get("ZONE", "")
        if not zone:
            raise EcountAPIError("NO_ZONE", "Zone 정보를 받지 못했습니다.")
        self._zone = zone
        return zone

    # ──────────────────────────────────────────────
    # 로그인
    # ──────────────────────────────────────────────

    def login(self, auto_zone: bool = True) -> dict:
        """Zone 조회 후 로그인. SESSION_ID를 내부에 저장."""
        if auto_zone and not self._zone:
            self.get_zone()

        url = f"{self._base_url}/OAPILogin"
        payload = {
            "COM_CODE": self.com_code,
            "USER_ID": self.user_id,
            "API_CERT_KEY": self.api_cert_key,
            "LAN_TYPE": self.lan_type,
            "ZONE": self._zone,
        }
        resp = self._session.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        self._raise_on_error(result)

        datas = result.get("Data", {}).get("Datas", {})
        self._session_id = datas.get("SESSION_ID")
        if not self._session_id:
            raise EcountAPIError("LOGIN_FAIL", "SESSION_ID를 받지 못했습니다.")
        return result

    # ──────────────────────────────────────────────
    # 기초등록 - 거래처
    # ──────────────────────────────────────────────

    def save_customer(self, payload: dict) -> dict:
        """거래처 등록/수정.

        payload 예시:
        {
            "CUST_CD": "C001",
            "CUST_NM": "테스트거래처",
            "CUST_TYPE": "1",        # 1=매출처, 2=매입처, 3=둘다
            "BUSINESS_NO": "123-45-67890",
            "CEO_NM": "홍길동",
            "TEL": "02-1234-5678",
            "EMAIL": "test@example.com",
            "ADDRESS": "서울시 강남구"
        }
        """
        return self._post("AccountBasic/SaveBasicCust", payload)

    # ──────────────────────────────────────────────
    # 기초등록 - 품목
    # ──────────────────────────────────────────────

    def save_product(self, payload: dict) -> dict:
        """품목 등록/수정.

        payload 예시:
        {
            "PROD_CD": "P001",
            "PROD_NM": "테스트품목",
            "UNIT": "EA",
            "IN_PRICE": 8000,
            "OUT_PRICE": 10000,
            "PROD_TYPE": "1",        # 1=재고관리, 2=비재고
            "CATEGORY_CD": ""
        }
        """
        return self._post("InventoryBasic/SaveBasicProduct", payload)

    def get_product(self, payload: dict) -> dict:
        """품목 단건 조회.

        payload 예시:
        {"PROD_CD": "P001"}
        """
        return self._post("InventoryBasic/ViewBasicProduct", payload)

    def get_product_list(self, payload: dict | None = None) -> dict:
        """품목 목록 조회.

        payload 예시:
        {
            "PROD_CD": "",
            "PROD_NM": "",
            "PAGE_SIZE": 100,
            "PAGE_NUM": 1
        }
        """
        return self._post("InventoryBasic/GetBasicProductsList", payload or {})

    # ──────────────────────────────────────────────
    # 영업관리 - 견적서
    # ──────────────────────────────────────────────

    def save_quotation(self, payload: dict) -> dict:
        """견적서 입력.

        payload 예시:
        {
            "IO_DATE": "20260514",
            "CUST_CD": "C001",
            "EMP_CD": "E001",
            "REMARK": "비고",
            "List": [
                {
                    "PROD_CD": "P001",
                    "QTY": 2,
                    "PRICE": 10000,
                    "SUPPLY_AMT": 20000,
                    "VAT": 2000,
                    "AMT": 22000
                }
            ]
        }
        """
        return self._post("Quotation/SaveQuotation", payload)

    # ──────────────────────────────────────────────
    # 영업관리 - 주문서(수주)
    # ──────────────────────────────────────────────

    def save_sale_order(self, payload: dict) -> dict:
        """주문서(수주) 입력.

        payload 예시:
        {
            "IO_DATE": "20260514",
            "CUST_CD": "C001",
            "EMP_CD": "E001",
            "DELIVERY_DATE": "20260521",
            "REMARK": "",
            "List": [
                {
                    "PROD_CD": "P001",
                    "QTY": 5,
                    "PRICE": 10000,
                    "SUPPLY_AMT": 50000,
                    "VAT": 5000,
                    "AMT": 55000
                }
            ]
        }
        """
        return self._post("SaleOrder/SaveSaleOrder", payload)

    # ──────────────────────────────────────────────
    # 영업관리 - 판매(매출)
    # ──────────────────────────────────────────────

    def save_sale(self, payload: dict) -> dict:
        """판매(매출) 입력.

        payload 예시:
        {
            "IO_DATE": "20260514",
            "CUST_CD": "C001",
            "EMP_CD": "E001",
            "TAX_TYPE": "A",         # A=과세, B=영세, C=면세
            "REMARK": "",
            "List": [
                {
                    "PROD_CD": "P001",
                    "WH_CD": "WH01",
                    "QTY": 3,
                    "PRICE": 10000,
                    "SUPPLY_AMT": 30000,
                    "VAT": 3000,
                    "AMT": 33000
                }
            ]
        }
        """
        return self._post("Sale/SaveSale", payload)

    # ──────────────────────────────────────────────
    # 구매관리 - 발주서
    # ──────────────────────────────────────────────

    def get_purchase_order_list(self, payload: dict | None = None) -> dict:
        """발주서 목록 조회.

        payload 예시:
        {
            "START_DATE": "20260501",
            "END_DATE": "20260514",
            "CUST_CD": "",
            "PAGE_SIZE": 100,
            "PAGE_NUM": 1
        }
        """
        return self._post("Purchases/GetPurchasesOrderList", payload or {
            "START_DATE": _month_start(),
            "END_DATE": _today(),
        })

    def save_purchases(self, payload: dict) -> dict:
        """구매(매입) 입력.

        payload 예시:
        {
            "IO_DATE": "20260514",
            "CUST_CD": "S001",
            "EMP_CD": "E001",
            "TAX_TYPE": "A",
            "REMARK": "",
            "List": [
                {
                    "PROD_CD": "P001",
                    "WH_CD": "WH01",
                    "QTY": 10,
                    "PRICE": 8000,
                    "SUPPLY_AMT": 80000,
                    "VAT": 8000,
                    "AMT": 88000
                }
            ]
        }
        """
        return self._post("Purchases/SavePurchases", payload)

    # ──────────────────────────────────────────────
    # 생산관리 - 작업지시서
    # ──────────────────────────────────────────────

    def save_job_order(self, payload: dict) -> dict:
        """작업지시서 입력.

        payload 예시:
        {
            "IO_DATE": "20260514",
            "PROD_CD": "P001",
            "QTY": 100,
            "WH_CD": "WH01",
            "EMP_CD": "E001",
            "REMARK": ""
        }
        """
        return self._post("JobOrder/SaveJobOrder", payload)

    # ──────────────────────────────────────────────
    # 생산관리 - 생산불출
    # ──────────────────────────────────────────────

    def save_goods_issued(self, payload: dict) -> dict:
        """생산불출 입력.

        payload 예시:
        {
            "IO_DATE": "20260514",
            "JOB_ORDER_NO": "JO2026051400001",
            "WH_CD": "WH01",
            "REMARK": "",
            "List": [
                {
                    "PROD_CD": "M001",
                    "QTY": 5,
                    "WH_CD": "WH01"
                }
            ]
        }
        """
        return self._post("GoodsIssued/SaveGoodsIssued", payload)

    # ──────────────────────────────────────────────
    # 생산관리 - 생산입고
    # ──────────────────────────────────────────────

    def save_goods_receipt(self, payload: dict) -> dict:
        """생산입고 입력.

        payload 예시:
        {
            "IO_DATE": "20260514",
            "JOB_ORDER_NO": "JO2026051400001",
            "PROD_CD": "P001",
            "QTY": 100,
            "WH_CD": "WH01",
            "REMARK": ""
        }
        """
        return self._post("GoodsReceipt/SaveGoodsReceipt", payload)

    # ──────────────────────────────────────────────
    # 회계 - 매출·매입전표 자동분개
    # ──────────────────────────────────────────────

    def save_invoice_auto(self, payload: dict) -> dict:
        """매출·매입전표 자동분개.

        payload 예시:
        {
            "SLIP_DATE": "20260514",
            "SLIP_TYPE": "1",        # 1=매출, 2=매입
            "SLIP_NO": "SL2026051400001",
            "REMARK": ""
        }
        """
        return self._post("InvoiceAuto/SaveInvoiceAuto", payload)

    # ──────────────────────────────────────────────
    # 재고현황
    # ──────────────────────────────────────────────

    def get_inventory_balance(self, payload: dict) -> dict:
        """재고현황 단건 조회.

        payload 예시:
        {
            "PROD_CD": "P001",
            "WH_CD": "",
            "BASE_DATE": "20260514"
        }
        """
        return self._post("InventoryBalance/ViewInventoryBalanceStatus", payload)

    def get_inventory_balance_list(self, payload: dict | None = None) -> dict:
        """재고현황 목록 조회.

        payload 예시:
        {
            "BASE_DATE": "20260514",
            "PROD_CD": "",
            "PAGE_SIZE": 100,
            "PAGE_NUM": 1
        }
        """
        return self._post("InventoryBalance/GetListInventoryBalanceStatus", payload or {
            "BASE_DATE": _today(),
        })

    def get_inventory_balance_by_location(self, payload: dict) -> dict:
        """창고별 재고현황 단건 조회.

        payload 예시:
        {
            "PROD_CD": "P001",
            "WH_CD": "WH01",
            "BASE_DATE": "20260514"
        }
        """
        return self._post("InventoryBalance/ViewInventoryBalanceStatusByLocation", payload)

    def get_inventory_balance_by_location_list(self, payload: dict | None = None) -> dict:
        """창고별 재고현황 목록 조회.

        payload 예시:
        {
            "BASE_DATE": "20260514",
            "WH_CD": "",
            "PAGE_SIZE": 100,
            "PAGE_NUM": 1
        }
        """
        return self._post("InventoryBalance/GetListInventoryBalanceStatusByLocation", payload or {
            "BASE_DATE": _today(),
        })

    # ──────────────────────────────────────────────
    # 쇼핑몰관리 - 주문 API
    # ──────────────────────────────────────────────

    def save_open_market_order(self, payload: dict) -> dict:
        """쇼핑몰 주문 등록.

        payload 예시:
        {
            "MALL_CD": "SMART",
            "ORDER_NO": "ORDER20260514001",
            "ORDER_DATE": "20260514",
            "CUST_NM": "홍길동",
            "TEL": "010-1234-5678",
            "ADDRESS": "서울시 강남구",
            "REMARK": "",
            "List": [
                {
                    "PROD_CD": "P001",
                    "QTY": 1,
                    "PRICE": 10000,
                    "AMT": 10000
                }
            ]
        }
        """
        return self._post("OpenMarket/SaveOpenMarketOrderNew", payload)

    # ──────────────────────────────────────────────
    # 근태관리 - 출퇴근
    # ──────────────────────────────────────────────

    def save_clock_in_out(self, payload: dict) -> dict:
        """출/퇴근 기록 등록.

        payload 예시:
        {
            "EMP_CD": "E001",
            "WORK_DATE": "20260514",
            "CLOCK_IN": "0900",      # HHmm
            "CLOCK_OUT": "1800",
            "REMARK": ""
        }
        """
        return self._post("TimeMgmt/SaveClockInOut", payload)

    # ──────────────────────────────────────────────
    # 게시판
    # ──────────────────────────────────────────────

    def save_board(self, payload: dict) -> dict:
        """게시판 글 등록.

        게시판 API는 별도 URL 체계를 사용합니다:
        https://oapi{ZONE}.ecount.com/ec5/api/app.oapi.v3/action/CreateOApiBoardAction

        payload 예시:
        {
            "BOARD_CD": "B001",
            "TITLE": "제목",
            "CONTENTS": "내용",
            "WRITER": "E001"
        }
        """
        if not self._session_id:
            raise EcountAPIError("NOT_LOGGED_IN", "login()을 먼저 호출하세요.")
        url = (
            f"https://oapi{self._zone}.ecount.com"
            f"/ec5/api/app.oapi.v3/action/CreateOApiBoardAction"
            f"?SESSION_ID={self._session_id}"
        )
        resp = self._session.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        self._raise_on_error(result)
        return result


# ──────────────────────────────────────────────
# 날짜 유틸
# ──────────────────────────────────────────────

def _today() -> str:
    return datetime.today().strftime("%Y%m%d")


def _month_start() -> str:
    return datetime.today().strftime("%Y%m01")
