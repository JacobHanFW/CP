# coupang_crawler.py
import undetected_chromedriver as uc
import time
import random
import urllib.parse
import re
from datetime import datetime
from bs4 import BeautifulSoup
import logging

# 로깅 설정
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class CoupangCrawler:
    """쿠팡 크롤링 클래스"""
    
    # User-Agent 설정
    UA_PC = "Mozilla/5.0 (Windows NT 10.0; Win64; x64)" \
            " AppleWebKit/537.36 (KHTML, like Gecko)" \
            " Chrome/138.0.0.0 Safari/537.36"
    UA_AND = "Mozilla/5.0 (Linux; Android 13; Pixel 6)" \
             " AppleWebKit/537.36 (KHTML, like Gecko)" \
             " Chrome/138.0.0.0 Mobile Safari/537.36"

    def __init__(self, platform="pc", incog=True, delay=6, headless=False):
        """
        크롤러 초기화
        
        Args:
            platform (str): 플랫폼 타입 ("pc" 또는 "android")
            incog (bool): 시크릿 모드 사용 여부
            delay (int): 요청 간 딜레이 시간 (초)
            headless (bool): 헤드리스 모드 사용 여부
        """
        self.platform = platform
        self.delay = delay
        self.driver = None
        self.incog = incog
        self.headless = headless
        self.ua = self.UA_PC if platform == "pc" else self.UA_AND
        self.win = "1920,1080" if platform == "pc" else "412,915"

    def _opts(self):
        """Chrome 옵션 설정"""
        o = uc.ChromeOptions()
        
        # 기본 옵션들
        if self.incog:
            o.add_argument("--incognito")
        if self.headless:
            o.add_argument("--headless=new")
        
        # 성능 및 안정성 옵션
        o.add_argument("--no-sandbox")
        o.add_argument("--disable-dev-shm-usage")
        o.add_argument("--disable-gpu")
        o.add_argument("--disable-extensions")
        o.add_argument("--disable-images")
        o.add_argument("--disable-blink-features=AutomationControlled")
        o.add_argument("--disable-web-security")
        o.add_argument("--disable-features=VizDisplayCompositor")
        
        # User-Agent 및 창 크기 설정
        o.add_argument(f"--user-agent={self.ua}")
        o.add_argument(f"--window-size={self.win}")
        o.add_argument("--page-load-strategy=eager")
        
        # 추가 탐지 우회 옵션
        o.add_experimental_option("excludeSwitches", ["enable-automation"])
        o.add_experimental_option('useAutomationExtension', False)
        
        return o

    def _build(self):
        """Chrome 드라이버 빌드"""
        try:
            self.driver = uc.Chrome(options=self._opts(), version_main=None)
            
            # 웹드라이버 탐지 방지 스크립트 실행
            self.driver.execute_script(
                "Object.defineProperty(navigator,'webdriver',{get:() => undefined});"
            )
            self.driver.execute_script(
                "Object.defineProperty(navigator,'plugins',{get:() => [1, 2, 3, 4, 5]});"
            )
            self.driver.execute_script(
                "Object.defineProperty(navigator,'languages',{get:() => ['ko-KR', 'ko', 'en-US', 'en']});"
            )
            
            # 페이지 로드 타임아웃 설정
            self.driver.set_page_load_timeout(30)
            
            return True
        except Exception as e:
            logger.error(f"{self.platform.upper()} 드라이버 생성 실패: {e}")
            return False

    @staticmethod
    def _ids(url):
        """URL에서 상품 ID 추출"""
        p = urllib.parse.urlparse(url)
        q = urllib.parse.parse_qs(p.query)
        
        # URL 경로에서 상품 ID 추출
        prod = next((x for x in p.path.split('/') if x.isdigit()), "")
        
        # 쿼리 파라미터에서 ID들 추출
        item_id = q.get("itemId", [""])[0]
        vendor_item_id = q.get("vendorItemId", [""])[0]
        
        return prod, item_id, vendor_item_id

    def _load(self, url):
        """페이지 로드"""
        for attempt in range(3):
            try:
                self.driver.get(url)
                time.sleep(random.uniform(self.delay, self.delay + 2))
                return True
            except Exception as e:
                logger.warning(f"페이지 로드 재시도 ({attempt + 1}/3): {e}")
                if attempt < 2:  # 마지막 시도가 아니면 잠시 대기
                    time.sleep(3)
        return False

    def rank(self, kw, tgt_url, pages=5):
        """
        키워드로 검색하여 대상 상품의 순위 찾기
        
        Args:
            kw (str): 검색 키워드
            tgt_url (str): 찾을 상품의 URL
            pages (int): 검색할 페이지 수
            
        Returns:
            dict: 검색 결과 또는 None
        """
        # 드라이버 빌드
        if not self._build():
            return None
        
        try:
            # 대상 상품의 ID들 추출
            prod, item, vend = self._ids(tgt_url)
            
            # 플랫폼별 검색 URL 설정
            if self.platform == "android":
                base = "https://m.coupang.com/nm/search?q="
            else:
                base = "https://www.coupang.com/np/search?q="
            
            # 페이지별 검색
            for p in range(1, pages + 1):
                url = f"{base}{urllib.parse.quote(kw)}&page={p}"
                
                if not self._load(url):
                    continue
                
                # HTML 파싱
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                
                # 플랫폼별 상품 카드 선택자
                if self.platform == "android":
                    sel = "li.plp-default__item"
                    cards = soup.select(sel)
                else:  # PC
                    selectors = [
                        "li.ProductUnit_productUnit__Qd6sv",
                        "dl[data-product-id]",
                        "li.search-product",
                        "div.search-product",
                        "li[data-product-id]",
                        "div[data-product-id]"
                    ]
                    cards = []
                    for selector in selectors:
                        cards = soup.select(selector)
                        if cards:
                            break
                
                if not cards:
                    logger.warning(f"상품 카드를 찾을 수 없습니다. 페이지 {p}")
                    continue
                
                # 순위 계산 (광고 제외)
                idx = 0
                for c in cards:
                    # 광고 필터링
                    ad_indicators = [
                        "span.ad-badge", 
                        "div.AdMark_adMark__KPMsC",
                        ".ad-product",
                        "[data-ad-id]",
                        ".sponsored"
                    ]
                    
                    is_ad = any(c.select_one(indicator) for indicator in ad_indicators)
                    if is_ad:
                        continue
                    
                    idx += 1
                    
                    # 데이터 추출
                    pd_id = c.get("data-product-id", "")
                    it_id = c.get("data-item-id", "")
                    vd_id = c.get("data-vendor-item-id", c.get("data-id", ""))
                    
                    # 링크에서 추가 정보 추출
                    link = c.find("a", href=True)
                    href = link["href"] if link else ""
                    
                    if href:
                        # 정규표현식으로 ID 추출
                        prod_match = re.search(r"/products/(\d+)", href)
                        item_match = re.search(r"itemId=(\d+)", href)
                        vendor_match = re.search(r"vendorItemId=(\d+)", href)
                        
                        if not pd_id and prod_match:
                            pd_id = prod_match.group(1)
                        if not it_id and item_match:
                            it_id = item_match.group(1)
                        if not vd_id and vendor_match:
                            vd_id = vendor_match.group(1)
                    
                    # ID 매칭 확인
                    match = (vd_id == vend or it_id == item or pd_id == prod)
                    
                    if match:
                        # 플랫폼별 상품명 추출
                        if self.platform == "android":
                            name_selectors = [
                                "strong.title",
                                ".prod-name", 
                                ".title"
                            ]
                        else:  # PC
                            name_selectors = [
                                ".ProductUnit_productName__gre7e",
                                "div.name",
                                ".prod-name",
                                "div[data-product-name]",
                                "a.prod-link div.name",
                                ".search-product-wrap .descriptions .name",
                                ".search-product-wrap .name",
                                ".product-name"
                            ]
                        
                        # 상품명 추출 시도
                        name_element = None
                        for selector in name_selectors:
                            name_element = c.select_one(selector)
                            if name_element:
                                break
                        
                        name_txt = name_element.get_text(strip=True) if name_element else "상품명 추출 실패"
                        
                        # 성공적으로 찾았으므로 결과 반환
                        result = {
                            "keyword": kw,
                            "platform": self.platform,
                            "rank": idx,
                            "page": p,
                            "product": name_txt,
                            "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                        }
                        
                        self.driver.quit()
                        return result
            
            # 모든 페이지 검색 후에도 찾지 못한 경우
            self.driver.quit()
            return None
            
        except Exception as e:
            logger.error(f"크롤링 중 오류 발생: {e}")
            if self.driver:
                self.driver.quit()
            return None

    def __del__(self):
        """소멸자: 드라이버 정리"""
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except:
                pass
