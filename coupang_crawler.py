# coupang_crawler.py 수정
import time
import random
import urllib.parse
import re
from datetime import datetime
from bs4 import BeautifulSoup
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

class CoupangCrawler:
    def __init__(self, platform="pc", incog=True, delay=8, headless=True):
        self.platform = platform
        self.delay = delay
        self.driver = None
        self.incog = incog
        self.headless = headless
        # 더 안정적인 User-Agent 사용
        self.ua = self._get_stable_ua()
        self.win = "1920,1080" if platform == "pc" else "412,915"

    def _get_stable_ua(self):
        """더 안정적인 User-Agent 반환"""
        if self.platform == "pc":
            return "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Safari/537.36"
        else:
            return "Mozilla/5.0 (Linux; Android 13; SM-G991B) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/119.0.0.0 Mobile Safari/537.36"

    def _opts(self):
        """개선된 Chrome 옵션"""
        options = Options()
        
        if self.incog:
            options.add_argument("--incognito")
        if self.headless:
            options.add_argument("--headless=new")
        
        # 안정성 옵션들
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-blink-features=AutomationControlled")
        
        # 성능 옵션들 (이미지는 유지)
        options.add_argument("--disable-web-security")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--allow-running-insecure-content")
        
        # User-Agent 및 창 크기
        options.add_argument(f"--user-agent={self.ua}")
        options.add_argument(f"--window-size={self.win}")
        
        # 탐지 우회
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        return options

    def _build(self):
        """개선된 드라이버 빌드"""
        try:
            options = self._opts()
            self.driver = webdriver.Chrome(options=options)
            
            # 웹드라이버 탐지 방지
            self.driver.execute_script(
                "Object.defineProperty(navigator,'webdriver',{get:() => undefined});"
            )
            self.driver.execute_script(
                "Object.defineProperty(navigator,'plugins',{get:() => [1, 2, 3, 4, 5]});"
            )
            
            # 타임아웃 설정
            self.driver.set_page_load_timeout(45)  # 더 긴 타임아웃
            self.driver.implicitly_wait(10)  # 암시적 대기 추가
            
            return True
        except Exception as e:
            logger.error(f"드라이버 생성 실패: {e}")
            return False

    def _load(self, url):
        """개선된 페이지 로드"""
        for attempt in range(3):
            try:
                self.driver.get(url)
                
                # 페이지 완전 로드 대기
                WebDriverWait(self.driver, 20).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                
                # 추가 대기 (JavaScript 렌더링 완료)
                time.sleep(random.uniform(self.delay, self.delay + 3))
                
                # 상품 카드가 로드되었는지 확인
                self._wait_for_products()
                
                return True
            except Exception as e:
                logger.warning(f"페이지 로드 재시도 ({attempt + 1}/3): {e}")
                if attempt < 2:
                    time.sleep(5)
        return False

    def _wait_for_products(self):
        """상품 카드 로드 대기"""
        try:
            if self.platform == "android":
                selectors = ["li.plp-default__item"]
            else:
                selectors = [
                    "li.ProductUnit_productUnit__Qd6sv",
                    "dl[data-product-id]",
                    "li.search-product",
                    "div.search-product"
                ]
            
            for selector in selectors:
                try:
                    WebDriverWait(self.driver, 15).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    break
                except:
                    continue
        except:
            pass  # 타임아웃되어도 계속 진행

    def rank(self, kw, tgt_url, pages=5):
        """개선된 순위 검색"""
        if not self._build():
            return None
        
        try:
            prod, item, vend = self._ids(tgt_url)
            
            # 검색 URL 생성
            if self.platform == "android":
                base = "https://m.coupang.com/nm/search?q="
            else:
                base = "https://www.coupang.com/np/search?q="
            
            for p in range(1, pages + 1):
                url = f"{base}{urllib.parse.quote(kw)}&page={p}"
                
                if not self._load(url):
                    continue
                
                # HTML 파싱
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                
                # 플랫폼별 상품 카드 찾기
                cards = self._find_product_cards(soup)
                
                if not cards:
                    logger.warning(f"상품 카드를 찾을 수 없습니다. 페이지 {p}")
                    # 페이지 소스 일부 출력 (디버깅용)
                    page_text = soup.get_text()[:500]
                    logger.info(f"페이지 내용 샘플: {page_text}")
                    continue
                
                # 순위 계산
                result = self._calculate_rank(cards, kw, p, prod, item, vend)
                if result:
                    self.driver.quit()
                    return result
            
            self.driver.quit()
            return None
            
        except Exception as e:
            logger.error(f"크롤링 중 오류: {e}")
            if self.driver:
                self.driver.quit()
            return None

    def _find_product_cards(self, soup):
        """플랫폼별 상품 카드 찾기"""
        if self.platform == "android":
            selectors = [
                "li.plp-default__item",
                ".search-product-item",
                "[data-product-id]"
            ]
        else:
            selectors = [
                "li.ProductUnit_productUnit__Qd6sv",
                "dl[data-product-id]",
                "li.search-product",
                "div.search-product",
                "li[data-product-id]",
                "div[data-product-id]",
                ".search-product-wrap"
            ]
        
        for selector in selectors:
            cards = soup.select(selector)
            if cards:
                logger.info(f"'{selector}' 선택자로 {len(cards)}개 상품 카드 발견")
                return cards
        
        return []

    def _calculate_rank(self, cards, kw, page, prod, item, vend):
        """순위 계산"""
        idx = 0
        
        for c in cards:
            # 광고 필터링 (더 포괄적)
            ad_indicators = [
                "span.ad-badge", 
                "div.AdMark_adMark__KPMsC",
                ".ad-product",
                "[data-ad-id]",
                ".sponsored",
                ".ad-label",
                "[data-impression-id]"
            ]
            
            is_ad = any(c.select_one(indicator) for indicator in ad_indicators)
            if is_ad:
                continue
            
            idx += 1
            
            # ID 추출 (더 포괄적)
            ids = self._extract_product_ids(c)
            
            # 매칭 확인
            if self._is_match(ids, prod, item, vend):
                name_txt = self._extract_product_name(c)
                
                return {
                    "keyword": kw,
                    "platform": self.platform,
                    "rank": idx,
                    "page": page,
                    "product": name_txt,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
        
        return None

    def _extract_product_ids(self, card):
        """상품 ID들 추출"""
        ids = {
            'product_id': card.get("data-product-id", ""),
            'item_id': card.get("data-item-id", ""),
            'vendor_id': card.get("data-vendor-item-id", card.get("data-id", ""))
        }
        
        # 링크에서도 ID 추출
        link = card.find("a", href=True)
        if link and link.get("href"):
            href = link["href"]
            
            prod_match = re.search(r"/products/(\d+)", href)
            item_match = re.search(r"itemId=(\d+)", href)
            vendor_match = re.search(r"vendorItemId=(\d+)", href)
            
            if not ids['product_id'] and prod_match:
                ids['product_id'] = prod_match.group(1)
            if not ids['item_id'] and item_match:
                ids['item_id'] = item_match.group(1)
            if not ids['vendor_id'] and vendor_match:
                ids['vendor_id'] = vendor_match.group(1)
        
        return ids

    def _is_match(self, ids, prod, item, vend):
        """ID 매칭 확인"""
        return (ids['vendor_id'] == vend or 
                ids['item_id'] == item or 
                ids['product_id'] == prod)

    def _extract_product_name(self, card):
        """상품명 추출"""
        if self.platform == "android":
            selectors = [
                "strong.title",
                ".prod-name",
                ".title",
                ".product-title"
            ]
        else:
            selectors = [
                ".ProductUnit_productName__gre7e",
                "div.name",
                ".prod-name",
                "div[data-product-name]",
                "a.prod-link div.name",
                ".search-product-wrap .descriptions .name",
                ".search-product-wrap .name",
                ".product-name",
                ".product-title"
            ]
        
        for selector in selectors:
            element = card.select_one(selector)
            if element:
                return element.get_text(strip=True)
        
        return "상품명 추출 실패"

    # 기존 메서드들 유지
    @staticmethod
    def _ids(url):
        """URL에서 상품 ID 추출"""
        p = urllib.parse.urlparse(url)
        q = urllib.parse.parse_qs(p.query)
        
        prod = next((x for x in p.path.split('/') if x.isdigit()), "")
        item_id = q.get("itemId", [""])[0]
        vendor_item_id = q.get("vendorItemId", [""])[0]
        
        return prod, item_id, vendor_item_id

    def __del__(self):
        if hasattr(self, 'driver') and self.driver:
            try:
                self.driver.quit()
            except:
                pass
