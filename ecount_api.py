"""
이카운트 OAPI V2 클라이언트
https://sboapiac.ecount.com/OAPI/V2/

사용법:
    from ecount_api import EcountAPI

    api = EcountAPI(com_code="159654", user_id="SLOCKIMPLANT", api_cert_key="YOUR_KEY")
    api.login()

    # 품목 목록 조회
    items = api.get_inventory_list()

    # 매출 등록
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
    def __init__(
        self,
        com_code: str,
        user_id: str,
        api_cert_key: str,
        lan_type: str = "ko-KR",
        zone: str = "AC",
    ):
        self.com_code = com_code
        self.user_id = user_id
        self.api_cert_key = api_cert_key
        self.lan_type = lan_type
        self.zone = zone

        self._session_id: Optional[str] = None
        self._set_cookie: Optional[str] = None
        self._host_url: Optional[str] = None
        self._session = requests.Session()

    # ──────────────────────────────────────────────
    # 내부 헬퍼
    # ──────────────────────────────────────────────

    @property
    def _base_url(self) -> str:
        host = self._host_url or "sboapiac.ecount.com"
        return f"https://{host}/OAPI/V2"

    def _post(self, path: str, data: dict) -> dict:
        if not self._session_id:
            raise EcountAPIError("NOT_LOGGED_IN", "login()을 먼저 호출하세요.")

        url = f"{self._base_url}/{path}"
        headers = {
            "Content-Type": "application/json",
            "Cookie": self._set_cookie,
        }
        payload = {
            "SESSION_ID": self._session_id,
            "COM_CODE": self.com_code,
            "USER_ID": self.user_id,
            "LAN_TYPE": self.lan_type,
            "ZONE": self.zone,
            **data,
        }
        resp = self._session.post(url, json=payload, headers=headers, timeout=30)
        resp.raise_for_status()
        result = resp.json()
        self._check_result(result)
        return result

    @staticmethod
    def _check_result(result: dict):
        status = result.get("Status")
        if status and str(status) != "200":
            data = result.get("Data", {})
            code = data.get("Code", str(status))
            msg = data.get("Msg", result.get("Message", "알 수 없는 오류"))
            raise EcountAPIError(code, msg)
        data = result.get("Data", {})
        if isinstance(data, dict) and data.get("Code") not in (None, "00", "0"):
            raise EcountAPIError(data.get("Code", "ERR"), data.get("Msg", "오류"))

    # ──────────────────────────────────────────────
    # 인증
    # ──────────────────────────────────────────────

    def login(self) -> dict:
        """로그인 및 세션 획득."""
        url = "https://sboapiac.ecount.com/OAPI/V2/OAPILogin"
        payload = {
            "COM_CODE": self.com_code,
            "USER_ID": self.user_id,
            "API_CERT_KEY": self.api_cert_key,
            "LAN_TYPE": self.lan_type,
            "ZONE": self.zone,
        }
        resp = self._session.post(url, json=payload, timeout=30)
        resp.raise_for_status()
        result = resp.json()

        data = result.get("Data", {}).get("Datas", {})
        self._session_id = data.get("SESSION_ID")
        self._set_cookie = data.get("SET_COOKIE")
        self._host_url = data.get("HOST_URL")

        if not self._session_id:
            raise EcountAPIError("LOGIN_FAIL", "세션 ID를 받지 못했습니다.")
        return result

    # ──────────────────────────────────────────────
    # 기초등록 - 품목
    # ──────────────────────────────────────────────

    def get_inventory_list(
        self,
        prod_cd: str = "",
        prod_nm: str = "",
        page_size: int = 100,
        page_num: int = 1,
    ) -> dict:
        """품목 목록 조회."""
        return self._post(
            "Inventory/GetInventoryList",
            {
                "Data": {
                    "PROD_CD": prod_cd,
                    "PROD_NM": prod_nm,
                    "PAGE_SIZE": page_size,
                    "PAGE_NUM": page_num,
                }
            },
        )

    def save_inventory(
        self,
        prod_cd: str,
        prod_nm: str,
        unit: str = "EA",
        in_price: float = 0,
        out_price: float = 0,
        category: str = "",
        remark: str = "",
    ) -> dict:
        """품목 등록/수정."""
        return self._post(
            "Inventory/SaveInventory",
            {
                "Data": {
                    "Datas": [
                        {
                            "PROD_CD": prod_cd,
                            "PROD_NM": prod_nm,
                            "UNIT": unit,
                            "IN_PRICE": in_price,
                            "OUT_PRICE": out_price,
                            "CATEGORY": category,
                            "REMARK": remark,
                        }
                    ]
                }
            },
        )

    def delete_inventory(self, prod_cd: str) -> dict:
        """품목 삭제."""
        return self._post(
            "Inventory/DeleteInventory",
            {"Data": {"Datas": [{"PROD_CD": prod_cd}]}},
        )

    # ──────────────────────────────────────────────
    # 기초등록 - 거래처
    # ──────────────────────────────────────────────

    def get_account_list(
        self,
        account_cd: str = "",
        account_nm: str = "",
        page_size: int = 100,
        page_num: int = 1,
    ) -> dict:
        """거래처 목록 조회."""
        return self._post(
            "Account/GetAccountList",
            {
                "Data": {
                    "ACCOUNT_CD": account_cd,
                    "ACCOUNT_NM": account_nm,
                    "PAGE_SIZE": page_size,
                    "PAGE_NUM": page_num,
                }
            },
        )

    def save_account(
        self,
        account_cd: str,
        account_nm: str,
        business_no: str = "",
        ceo_nm: str = "",
        tel: str = "",
        email: str = "",
        address: str = "",
        remark: str = "",
    ) -> dict:
        """거래처 등록/수정."""
        return self._post(
            "Account/SaveAccount",
            {
                "Data": {
                    "Datas": [
                        {
                            "ACCOUNT_CD": account_cd,
                            "ACCOUNT_NM": account_nm,
                            "BUSINESS_NO": business_no,
                            "CEO_NM": ceo_nm,
                            "TEL": tel,
                            "EMAIL": email,
                            "ADDRESS": address,
                            "REMARK": remark,
                        }
                    ]
                }
            },
        )

    def delete_account(self, account_cd: str) -> dict:
        """거래처 삭제."""
        return self._post(
            "Account/DeleteAccount",
            {"Data": {"Datas": [{"ACCOUNT_CD": account_cd}]}},
        )

    # ──────────────────────────────────────────────
    # 기초등록 - 창고
    # ──────────────────────────────────────────────

    def get_warehouse_list(self, wh_cd: str = "", wh_nm: str = "") -> dict:
        """창고 목록 조회."""
        return self._post(
            "WareHouse/GetWareHouseList",
            {"Data": {"WH_CD": wh_cd, "WH_NM": wh_nm}},
        )

    def save_warehouse(
        self,
        wh_cd: str,
        wh_nm: str,
        remark: str = "",
    ) -> dict:
        """창고 등록/수정."""
        return self._post(
            "WareHouse/SaveWareHouse",
            {
                "Data": {
                    "Datas": [{"WH_CD": wh_cd, "WH_NM": wh_nm, "REMARK": remark}]
                }
            },
        )

    # ──────────────────────────────────────────────
    # 기초등록 - 직원
    # ──────────────────────────────────────────────

    def get_employee_list(self, emp_cd: str = "", emp_nm: str = "") -> dict:
        """직원 목록 조회."""
        return self._post(
            "Employee/GetEmployeeList",
            {"Data": {"EMP_CD": emp_cd, "EMP_NM": emp_nm}},
        )

    def save_employee(
        self,
        emp_cd: str,
        emp_nm: str,
        dept_cd: str = "",
        position: str = "",
        tel: str = "",
        email: str = "",
    ) -> dict:
        """직원 등록/수정."""
        return self._post(
            "Employee/SaveEmployee",
            {
                "Data": {
                    "Datas": [
                        {
                            "EMP_CD": emp_cd,
                            "EMP_NM": emp_nm,
                            "DEPT_CD": dept_cd,
                            "POSITION": position,
                            "TEL": tel,
                            "EMAIL": email,
                        }
                    ]
                }
            },
        )

    # ──────────────────────────────────────────────
    # 영업관리 - 견적서
    # ──────────────────────────────────────────────

    def get_sale_quot_list(
        self,
        start_date: str = "",
        end_date: str = "",
        account_cd: str = "",
        page_size: int = 100,
        page_num: int = 1,
    ) -> dict:
        """견적서 목록 조회. 날짜 형식: YYYYMMDD"""
        return self._post(
            "Sale/GetSaleQuotList",
            {
                "Data": {
                    "START_DATE": start_date or _today(),
                    "END_DATE": end_date or _today(),
                    "ACCOUNT_CD": account_cd,
                    "PAGE_SIZE": page_size,
                    "PAGE_NUM": page_num,
                }
            },
        )

    def save_sale_quot(
        self,
        account_cd: str,
        items: list[dict],
        quot_date: str = "",
        remark: str = "",
        emp_cd: str = "",
    ) -> dict:
        """견적서 등록.

        items: [{"PROD_CD": "P001", "QTY": 2, "PRICE": 10000, "UNIT": "EA"}, ...]
        """
        return self._post(
            "Sale/SaveSaleQuot",
            {
                "Data": {
                    "Datas": [
                        {
                            "ACCOUNT_CD": account_cd,
                            "QUOT_DATE": quot_date or _today(),
                            "EMP_CD": emp_cd,
                            "REMARK": remark,
                            "Details": items,
                        }
                    ]
                }
            },
        )

    # ──────────────────────────────────────────────
    # 영업관리 - 수주
    # ──────────────────────────────────────────────

    def get_sale_order_list(
        self,
        start_date: str = "",
        end_date: str = "",
        account_cd: str = "",
        page_size: int = 100,
        page_num: int = 1,
    ) -> dict:
        """수주 목록 조회."""
        return self._post(
            "Sale/GetSaleOrderList",
            {
                "Data": {
                    "START_DATE": start_date or _today(),
                    "END_DATE": end_date or _today(),
                    "ACCOUNT_CD": account_cd,
                    "PAGE_SIZE": page_size,
                    "PAGE_NUM": page_num,
                }
            },
        )

    def save_sale_order(
        self,
        account_cd: str,
        items: list[dict],
        order_date: str = "",
        delivery_date: str = "",
        emp_cd: str = "",
        remark: str = "",
    ) -> dict:
        """수주 등록."""
        return self._post(
            "Sale/SaveSaleOrder",
            {
                "Data": {
                    "Datas": [
                        {
                            "ACCOUNT_CD": account_cd,
                            "ORDER_DATE": order_date or _today(),
                            "DELIVERY_DATE": delivery_date,
                            "EMP_CD": emp_cd,
                            "REMARK": remark,
                            "Details": items,
                        }
                    ]
                }
            },
        )

    # ──────────────────────────────────────────────
    # 영업관리 - 출고
    # ──────────────────────────────────────────────

    def get_sale_delivery_list(
        self,
        start_date: str = "",
        end_date: str = "",
        account_cd: str = "",
        page_size: int = 100,
        page_num: int = 1,
    ) -> dict:
        """출고 목록 조회."""
        return self._post(
            "Sale/GetSaleDeliveryList",
            {
                "Data": {
                    "START_DATE": start_date or _today(),
                    "END_DATE": end_date or _today(),
                    "ACCOUNT_CD": account_cd,
                    "PAGE_SIZE": page_size,
                    "PAGE_NUM": page_num,
                }
            },
        )

    def save_sale_delivery(
        self,
        account_cd: str,
        items: list[dict],
        delivery_date: str = "",
        wh_cd: str = "",
        emp_cd: str = "",
        remark: str = "",
    ) -> dict:
        """출고 등록.

        items: [{"PROD_CD": "P001", "QTY": 2, "PRICE": 10000, "WH_CD": "WH01"}, ...]
        """
        return self._post(
            "Sale/SaveSaleDelivery",
            {
                "Data": {
                    "Datas": [
                        {
                            "ACCOUNT_CD": account_cd,
                            "DELIVERY_DATE": delivery_date or _today(),
                            "WH_CD": wh_cd,
                            "EMP_CD": emp_cd,
                            "REMARK": remark,
                            "Details": items,
                        }
                    ]
                }
            },
        )

    # ──────────────────────────────────────────────
    # 영업관리 - 매출
    # ──────────────────────────────────────────────

    def get_sale_list(
        self,
        start_date: str = "",
        end_date: str = "",
        account_cd: str = "",
        page_size: int = 100,
        page_num: int = 1,
    ) -> dict:
        """매출 목록 조회."""
        return self._post(
            "Sale/GetSaleList",
            {
                "Data": {
                    "START_DATE": start_date or _today(),
                    "END_DATE": end_date or _today(),
                    "ACCOUNT_CD": account_cd,
                    "PAGE_SIZE": page_size,
                    "PAGE_NUM": page_num,
                }
            },
        )

    def save_sale(
        self,
        account_cd: str,
        items: list[dict],
        sale_date: str = "",
        tax_type: str = "A",
        emp_cd: str = "",
        remark: str = "",
    ) -> dict:
        """매출 등록.

        tax_type: "A"=과세, "B"=영세, "C"=면세
        items: [{"PROD_CD": "P001", "QTY": 1, "PRICE": 10000, "SUPPLY_AMT": 10000, "VAT": 1000}, ...]
        """
        return self._post(
            "Sale/SaveSale",
            {
                "Data": {
                    "Datas": [
                        {
                            "ACCOUNT_CD": account_cd,
                            "SALE_DATE": sale_date or _today(),
                            "TAX_TYPE": tax_type,
                            "EMP_CD": emp_cd,
                            "REMARK": remark,
                            "Details": items,
                        }
                    ]
                }
            },
        )

    # ──────────────────────────────────────────────
    # 영업관리 - 수금
    # ──────────────────────────────────────────────

    def get_sale_receipt_list(
        self,
        start_date: str = "",
        end_date: str = "",
        account_cd: str = "",
        page_size: int = 100,
        page_num: int = 1,
    ) -> dict:
        """수금 목록 조회."""
        return self._post(
            "Sale/GetSaleReceiptList",
            {
                "Data": {
                    "START_DATE": start_date or _today(),
                    "END_DATE": end_date or _today(),
                    "ACCOUNT_CD": account_cd,
                    "PAGE_SIZE": page_size,
                    "PAGE_NUM": page_num,
                }
            },
        )

    def save_sale_receipt(
        self,
        account_cd: str,
        amount: float,
        receipt_date: str = "",
        payment_type: str = "11",
        bank_cd: str = "",
        remark: str = "",
    ) -> dict:
        """수금 등록.

        payment_type: "11"=현금, "12"=수표, "21"=어음, "22"=전자어음,
                      "31"=외상, "41"=카드, "51"=계좌이체
        """
        return self._post(
            "Sale/SaveSaleReceipt",
            {
                "Data": {
                    "Datas": [
                        {
                            "ACCOUNT_CD": account_cd,
                            "RECEIPT_DATE": receipt_date or _today(),
                            "PAYMENT_TYPE": payment_type,
                            "AMOUNT": amount,
                            "BANK_CD": bank_cd,
                            "REMARK": remark,
                        }
                    ]
                }
            },
        )

    # ──────────────────────────────────────────────
    # 구매관리 - 발주
    # ──────────────────────────────────────────────

    def get_buy_order_list(
        self,
        start_date: str = "",
        end_date: str = "",
        account_cd: str = "",
        page_size: int = 100,
        page_num: int = 1,
    ) -> dict:
        """발주 목록 조회."""
        return self._post(
            "Buy/GetBuyOrderList",
            {
                "Data": {
                    "START_DATE": start_date or _today(),
                    "END_DATE": end_date or _today(),
                    "ACCOUNT_CD": account_cd,
                    "PAGE_SIZE": page_size,
                    "PAGE_NUM": page_num,
                }
            },
        )

    def save_buy_order(
        self,
        account_cd: str,
        items: list[dict],
        order_date: str = "",
        delivery_date: str = "",
        emp_cd: str = "",
        remark: str = "",
    ) -> dict:
        """발주 등록.

        items: [{"PROD_CD": "P001", "QTY": 10, "PRICE": 8000, "UNIT": "EA"}, ...]
        """
        return self._post(
            "Buy/SaveBuyOrder",
            {
                "Data": {
                    "Datas": [
                        {
                            "ACCOUNT_CD": account_cd,
                            "ORDER_DATE": order_date or _today(),
                            "DELIVERY_DATE": delivery_date,
                            "EMP_CD": emp_cd,
                            "REMARK": remark,
                            "Details": items,
                        }
                    ]
                }
            },
        )

    # ──────────────────────────────────────────────
    # 구매관리 - 입고
    # ──────────────────────────────────────────────

    def get_buy_delivery_list(
        self,
        start_date: str = "",
        end_date: str = "",
        account_cd: str = "",
        page_size: int = 100,
        page_num: int = 1,
    ) -> dict:
        """입고 목록 조회."""
        return self._post(
            "Buy/GetBuyDeliveryList",
            {
                "Data": {
                    "START_DATE": start_date or _today(),
                    "END_DATE": end_date or _today(),
                    "ACCOUNT_CD": account_cd,
                    "PAGE_SIZE": page_size,
                    "PAGE_NUM": page_num,
                }
            },
        )

    def save_buy_delivery(
        self,
        account_cd: str,
        items: list[dict],
        delivery_date: str = "",
        wh_cd: str = "",
        emp_cd: str = "",
        remark: str = "",
    ) -> dict:
        """입고 등록.

        items: [{"PROD_CD": "P001", "QTY": 10, "PRICE": 8000, "WH_CD": "WH01"}, ...]
        """
        return self._post(
            "Buy/SaveBuyDelivery",
            {
                "Data": {
                    "Datas": [
                        {
                            "ACCOUNT_CD": account_cd,
                            "DELIVERY_DATE": delivery_date or _today(),
                            "WH_CD": wh_cd,
                            "EMP_CD": emp_cd,
                            "REMARK": remark,
                            "Details": items,
                        }
                    ]
                }
            },
        )

    # ──────────────────────────────────────────────
    # 구매관리 - 매입
    # ──────────────────────────────────────────────

    def get_buy_list(
        self,
        start_date: str = "",
        end_date: str = "",
        account_cd: str = "",
        page_size: int = 100,
        page_num: int = 1,
    ) -> dict:
        """매입 목록 조회."""
        return self._post(
            "Buy/GetBuyList",
            {
                "Data": {
                    "START_DATE": start_date or _today(),
                    "END_DATE": end_date or _today(),
                    "ACCOUNT_CD": account_cd,
                    "PAGE_SIZE": page_size,
                    "PAGE_NUM": page_num,
                }
            },
        )

    def save_buy(
        self,
        account_cd: str,
        items: list[dict],
        buy_date: str = "",
        tax_type: str = "A",
        emp_cd: str = "",
        remark: str = "",
    ) -> dict:
        """매입 등록.

        tax_type: "A"=과세, "B"=영세, "C"=면세
        items: [{"PROD_CD": "P001", "QTY": 10, "PRICE": 8000, "SUPPLY_AMT": 80000, "VAT": 8000}, ...]
        """
        return self._post(
            "Buy/SaveBuy",
            {
                "Data": {
                    "Datas": [
                        {
                            "ACCOUNT_CD": account_cd,
                            "BUY_DATE": buy_date or _today(),
                            "TAX_TYPE": tax_type,
                            "EMP_CD": emp_cd,
                            "REMARK": remark,
                            "Details": items,
                        }
                    ]
                }
            },
        )

    # ──────────────────────────────────────────────
    # 구매관리 - 지급
    # ──────────────────────────────────────────────

    def get_buy_payment_list(
        self,
        start_date: str = "",
        end_date: str = "",
        account_cd: str = "",
        page_size: int = 100,
        page_num: int = 1,
    ) -> dict:
        """지급 목록 조회."""
        return self._post(
            "Buy/GetBuyPaymentList",
            {
                "Data": {
                    "START_DATE": start_date or _today(),
                    "END_DATE": end_date or _today(),
                    "ACCOUNT_CD": account_cd,
                    "PAGE_SIZE": page_size,
                    "PAGE_NUM": page_num,
                }
            },
        )

    def save_buy_payment(
        self,
        account_cd: str,
        amount: float,
        payment_date: str = "",
        payment_type: str = "11",
        bank_cd: str = "",
        remark: str = "",
    ) -> dict:
        """지급 등록.

        payment_type: "11"=현금, "12"=수표, "21"=어음, "22"=전자어음,
                      "31"=외상, "41"=카드, "51"=계좌이체
        """
        return self._post(
            "Buy/SaveBuyPayment",
            {
                "Data": {
                    "Datas": [
                        {
                            "ACCOUNT_CD": account_cd,
                            "PAYMENT_DATE": payment_date or _today(),
                            "PAYMENT_TYPE": payment_type,
                            "AMOUNT": amount,
                            "BANK_CD": bank_cd,
                            "REMARK": remark,
                        }
                    ]
                }
            },
        )

    # ──────────────────────────────────────────────
    # 출력물 API
    # ──────────────────────────────────────────────

    def get_print_list(self, print_type: str = "") -> dict:
        """출력물 양식 목록 조회.

        print_type: 빈값=전체, "SALE"=매출, "BUY"=매입, "DELIVERY"=출고입고 등
        """
        return self._post(
            "Print/GetPrintList",
            {"Data": {"PRINT_TYPE": print_type}},
        )

    def get_print_url(
        self,
        menu_type: str,
        slip_no: str,
        form_cd: str = "",
    ) -> dict:
        """전표 출력 URL 조회.

        menu_type: "SALE"=매출, "BUY"=매입, "SALE_QUOT"=견적서,
                   "SALE_ORDER"=수주, "BUY_ORDER"=발주,
                   "SALE_DELIVERY"=출고, "BUY_DELIVERY"=입고
        slip_no: 전표번호
        form_cd: 출력 양식 코드 (빈값=기본양식)
        """
        return self._post(
            "Print/GetPrintUrl",
            {
                "Data": {
                    "MENU_TYPE": menu_type,
                    "SLIP_NO": slip_no,
                    "FORM_CD": form_cd,
                }
            },
        )

    def get_print_preview_url(
        self,
        menu_type: str,
        slip_no: str,
        form_cd: str = "",
    ) -> str:
        """출력 미리보기 URL 반환."""
        result = self.get_print_url(menu_type, slip_no, form_cd)
        return result.get("Data", {}).get("Datas", {}).get("PRINT_URL", "")

    def get_tax_invoice_list(
        self,
        start_date: str = "",
        end_date: str = "",
        account_cd: str = "",
        page_size: int = 100,
        page_num: int = 1,
    ) -> dict:
        """세금계산서 목록 조회."""
        return self._post(
            "TaxInvoice/GetTaxInvoiceList",
            {
                "Data": {
                    "START_DATE": start_date or _today(),
                    "END_DATE": end_date or _today(),
                    "ACCOUNT_CD": account_cd,
                    "PAGE_SIZE": page_size,
                    "PAGE_NUM": page_num,
                }
            },
        )

    def issue_tax_invoice(
        self,
        slip_no: str,
        issue_type: str = "1",
    ) -> dict:
        """세금계산서 발행.

        issue_type: "1"=즉시발행, "2"=임시저장
        slip_no: 매출 전표번호
        """
        return self._post(
            "TaxInvoice/IssueTaxInvoice",
            {
                "Data": {
                    "Datas": [{"SLIP_NO": slip_no, "ISSUE_TYPE": issue_type}]
                }
            },
        )

    def get_statement_print_url(
        self,
        account_cd: str,
        start_date: str = "",
        end_date: str = "",
        form_cd: str = "",
    ) -> dict:
        """거래명세서 출력 URL 조회."""
        return self._post(
            "Print/GetStatementPrintUrl",
            {
                "Data": {
                    "ACCOUNT_CD": account_cd,
                    "START_DATE": start_date or _today(),
                    "END_DATE": end_date or _today(),
                    "FORM_CD": form_cd,
                }
            },
        )


# ──────────────────────────────────────────────
# 유틸
# ──────────────────────────────────────────────

def _today() -> str:
    return datetime.today().strftime("%Y%m%d")
