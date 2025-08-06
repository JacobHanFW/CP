# coupang_crawler.py - 디버깅 강화 버전
import time
import random
import urllib.parse
import re
import os
from datetime import datetime
from bs4 import BeautifulSoup
import logging
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 로깅 설정
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CoupangCrawler:
    def __init__(self, platform="pc", incog=True, delay=8, headless=True):
        self.platform = platform
        self.delay = delay
        self.driver = None
        self.incog = incog
        self.headless = headless
        self.ua = self._get_stable_ua()
        self.win = "1920,1080" if platform == "pc" else "412,915"
        self.screenshot_count = 0

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
        
        # 기본 옵션들
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--disable-web-security")
        options.add_argument("--ignore-certificate-errors")
        options.add_argument("--allow-running-insecure-content")
        
        # User-Agent 및 창 크기
        options.add_argument(f"--user-agent={self.ua}")
        options.add_argument(f"--window-size={self.win}")
        
        # 탐지 우회 옵션
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        
        logger.info(f"🔧 Chrome 옵션 설정 완료 - 플랫폼: {self.platform}, 헤드리스: {self.headless}")
        
        return options

    def _build(self):
        """개선된 드라이버 빌드"""
        logger.info(f"🚀 Chrome 드라이버 생성 시작 - {self.platform}")
        try:
            options = self._opts()
            self.driver = webdriver.Chrome(options=options)
            
            # 웹드라이버 탐지 방지 스크립트
            logger.info("🛡️ 웹드라이버 탐지 방지 스크립트 실행")
            self.driver.execute_script(
                "Object.defineProperty(navigator,'webdriver',{get:() => undefined});"
            )
            self.driver.execute_script(
                "Object.defineProperty(navigator,'plugins',{get:() => [1, 2, 3, 4, 5]});"
            )
            
            # 타임아웃 설정
            self.driver.set_page_load_timeout(45)
            self.driver.implicitly_wait(10)
            
            logger.info("✅ Chrome 드라이버 생성 성공")
            return True
            
        except Exception as e:
            logger.error(f"❌ 드라이버 생성 실패: {e}")
            return False

    def _take_screenshot(self, filename_prefix="debug"):
        """스크린샷 캡처"""
        try:
            self.screenshot_count += 1
            timestamp = datetime.now().strftime("%H%M%S")
            filename = f"/tmp/{filename_prefix}_{self.platform}_{timestamp}_{self.screenshot_count}.png"
            
            self.driver.save_screenshot(filename)
            logger.info(f"📸 스크린샷 저장: {filename}")
            return filename
        except Exception as e:
            logger.warning(f"📸 스크린샷 저장 실패: {e}")
            return None

    def _load(self, url):
        """개선된 페이지 로드 - 스크린샷 포함"""
        logger.info(f"🌐 페이지 로드 시작: {url}")
        
        for attempt in range(3):
            try:
                logger.info(f"📡 시도 {attempt + 1}/3: 페이지 요청 중...")
                self.driver.get(url)
                
                # 페이지 로드 완료 대기
                logger.info("⏳ 페이지 로드 완료 대기 중...")
                WebDriverWait(self.driver, 20).until(
                    lambda driver: driver.execute_script("return document.readyState") == "complete"
                )
                
                # 로드 후 스크린샷
                self._take_screenshot(f"loaded_page_{attempt}")
                
                # 페이지 기본 정보 수집
                try:
                    page_title = self.driver.title
                    current_url = self.driver.current_url
                    page_source_length = len(self.driver.page_source)
                    
                    logger.info(f"📋 페이지 정보:")
                    logger.info(f"   - 제목: {page_title}")
                    logger.info(f"   - 현재 URL: {current_url}")
                    logger.info(f"   - HTML 크기: {page_source_length:,} bytes")
                    
                    # CAPTCHA 또는 차단 확인
                    page_text = self.driver.page_source.lower()
                    if any(keyword in page_text for keyword in ['captcha', '로봇이 아닙니다', 'robot', 'verification']):
                        logger.error("🚫 CAPTCHA 또는 접근 제한 페이지 감지됨!")
                        self._take_screenshot(f"captcha_detected_{attempt}")
                        
                except Exception as e:
                    logger.warning(f"페이지 정보 수집 중 오류: {e}")
                
                # 딜레이 적용
                wait_time = random.uniform(self.delay, self.delay + 3)
                logger.info(f"😴 {wait_time:.1f}초 대기 중...")
                time.sleep(wait_time)
                
                # 상품 로드 대기
                self._wait_for_products()
                
                logger.info("✅ 페이지 로드 성공")
                return True
                
            except Exception as e:
                logger.warning(f"⚠️ 페이지 로드 시도 {attempt + 1} 실패: {e}")
                if attempt < 2:
                    logger.info(f"🔄 5초 후 재시도...")
                    time.sleep(5)
                else:
                    logger.error("❌ 모든 페이지 로드 시도 실패")
                    
        return False

    def _wait_for_products(self):
        """상품 카드 로드 대기"""
        logger.info("🛍️ 상품 카드 로드 대기 중...")
        
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
            
            for i, selector in enumerate(selectors):
                try:
                    logger.info(f"🔍 선택자 {i+1}/{len(selectors)} 시도: {selector}")
                    WebDriverWait(self.driver, 10).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    logger.info(f"✅ 상품 카드 발견: {selector}")
                    return
                except:
                    logger.info(f"❌ 선택자 실패: {selector}")
                    continue
                    
            logger.warning("⚠️ 모든 선택자로 상품 카드를 찾지 못함")
            
        except Exception as e:
            logger.warning(f"상품 로드 대기 중 오류: {e}")

    def rank(self, kw, tgt_url, pages=5):
        """개선된 순위 검색 - 디버깅 강화 버전"""
        logger.info("="*60)
        logger.info(f"🚀 크롤링 시작")
        logger.info(f"   - 키워드: {kw}")
        logger.info(f"   - 플랫폼: {self.platform}")
        logger.info(f"   - 대상 URL: {tgt_url}")
        logger.info(f"   - 검색 페이지: {pages}")
        logger.info("="*60)
        
        if not self._build():
            logger.error("❌ 드라이버 빌드 실패")
            return None
        
        try:
            # URL에서 ID 추출
            prod, item, vend = self._ids(tgt_url)
            logger.info(f"🆔 추출된 ID:")
            logger.info(f"   - Product ID: {prod}")
            logger.info(f"   - Item ID: {item}")
            logger.info(f"   - Vendor Item ID: {vend}")
            
            # 검색 URL 베이스 설정
            if self.platform == "android":
                base = "https://m.coupang.com/nm/search?q="
                logger.info("📱 모바일 검색 모드")
            else:
                base = "https://www.coupang.com/np/search?q="
                logger.info("💻 PC 검색 모드")
            
            # 페이지별 검색
            for p in range(1, pages + 1):
                logger.info(f"\n📄 페이지 {p}/{pages} 검색 시작")
                logger.info("-" * 40)
                
                url = f"{base}{urllib.parse.quote(kw)}&page={p}"
                logger.info(f"🔗 검색 URL: {url}")
                
                if not self._load(url):
                    logger.warning(f"⚠️ 페이지 {p} 로드 실패 - 다음 페이지로 이동")
                    continue
                
                # HTML 파싱
                soup = BeautifulSoup(self.driver.page_source, "html.parser")
                
                # 상품 카드 찾기
                cards = self._find_product_cards(soup, p)
                
                if not cards:
                    logger.warning(f"❌ 페이지 {p}에서 상품 카드를 찾지 못함")
                    
                    # 디버깅 정보 수집
                    page_text = soup.get_text()
                    logger.info(f"📝 페이지 텍스트 길이: {len(page_text)}")
                    
                    # 키워드가 페이지에 있는지 확인
                    if kw.lower() in page_text.lower():
                        logger.info(f"✅ 키워드 '{kw}' 페이지에서 발견됨")
                    else:
                        logger.warning(f"❌ 키워드 '{kw}' 페이지에서 발견되지 않음")
                    
                    # 페이지 샘플 텍스트 로깅
                    sample_text = page_text[:1000].replace('\n', ' ').strip()
                    logger.info(f"📄 페이지 내용 샘플: {sample_text}")
                    
                    # 스크린샷 저장
                    self._take_screenshot(f"no_products_page_{p}")
                    continue
                
                # 순위 계산
                result = self._calculate_rank(cards, kw, p, prod, item, vend)
                if result:
                    logger.info(f"🎯 순위 발견!")
                    logger.info(f"   - 순위: {result['rank']}위")
                    logger.info(f"   - 페이지: {result['page']}")
                    logger.info(f"   - 상품명: {result['product']}")
                    
                    # 성공 스크린샷
                    self._take_screenshot(f"found_rank_{result['rank']}")
                    
                    self.driver.quit()
                    return result
                else:
                    logger.info(f"❌ 페이지 {p}에서 대상 상품 미발견")
            
            logger.info("🔍 모든 페이지 검색 완료 - 대상 상품을 찾지 못함")
            self.driver.quit()
            return None
            
        except Exception as e:
            logger.error(f"💥 크롤링 중 치명적 오류: {e}")
            logger.exception("상세 오류 정보:")
            
            # 오류 스크린샷
            self._take_screenshot("error_occurred")
            
            if self.driver:
                self.driver.quit()
            return None

    def _find_product_cards(self, soup, page_num):
        """플랫폼별 상품 카드 찾기 - 디버깅 강화"""
        logger.info(f"🔍 페이지 {page_num}에서 상품 카드 검색 중...")
        
        if self.platform == "android":
            selectors = [
                "li.plp-default__item",
                ".search-product-item",
                "[data-product-id]",
                ".product-item"
            ]
        else:
            selectors = [
                "li.ProductUnit_productUnit__Qd6sv",
                "dl[data-product-id]",
                "li.search-product",
                "div.search-product",
                "li[data-product-id]",
                "div[data-product-id]",
                ".search-product-wrap",
                ".product-item"
            ]
        
        for i, selector in enumerate(selectors):
            logger.info(f"🎯 선택자 {i+1}/{len(selectors)} 시도: {selector}")
            cards = soup.select(selector)
            
            if cards:
                logger.info(f"✅ '{selector}' 선택자로 {len(cards)}개 상품 카드 발견")
                
                # 각 카드의 기본 정보 로깅
                for j, card in enumerate(cards[:3]):  # 처음 3개만 샘플링
                    card_text = card.get_text(strip=True)[:100]
                    logger.info(f"   📦 카드 {j+1}: {card_text}...")
                
                return cards
            else:
                logger.info(f"❌ '{selector}' 선택자로 상품 카드 없음")
        
        logger.warning("⚠️ 모든 선택자로 상품 카드를 찾지 못함")
        return []

    def _calculate_rank(self, cards, kw, page, prod, item, vend):
        """순위 계산 - 디버깅 강화"""
        logger.info(f"🧮 순위 계산 시작 - {len(cards)}개 카드 분석")
        
        idx = 0
        ad_count = 0
        
        for card_num, c in enumerate(cards, 1):
            logger.info(f"🔍 카드 {card_num}/{len(cards)} 분석 중...")
            
            # 광고 필터링
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
                ad_count += 1
                logger.info(f"   📢 광고 상품 - 순위에서 제외 (광고 {ad_count}개)")
                continue
            
            idx += 1
            logger.info(f"   🏆 순위 {idx}: 일반 상품")
            
            # 상품 ID 추출
            ids = self._extract_product_ids(c)
            logger.info(f"   🆔 추출된 ID - Product: {ids['product_id']}, Item: {ids['item_id']}, Vendor: {ids['vendor_id']}")
            
            # 매칭 확인
            if self._is_match(ids, prod, item, vend):
                logger.info(f"   🎯 대상 상품 매칭 성공!")
                
                name_txt = self._extract_product_name(c)
                logger.info(f"   📦 상품명: {name_txt}")
                
                result = {
                    "keyword": kw,
                    "platform": self.platform,
                    "rank": idx,
                    "page": page,
                    "product": name_txt,
                    "time": datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                }
                
                return result
            else:
                logger.info(f"   ❌ 대상 상품 불일치")
        
        logger.info(f"📊 페이지 {page} 분석 완료 - 총 {idx}개 일반 상품, {ad_count}개 광고 상품")
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
        match_vendor = ids['vendor_id'] == vend and vend != ""
        match_item = ids['item_id'] == item and item != ""
        match_product = ids['product_id'] == prod and prod != ""
        
        if match_vendor:
            logger.info(f"   ✅ Vendor ID 매칭: {vend}")
        if match_item:
            logger.info(f"   ✅ Item ID 매칭: {item}")
        if match_product:
            logger.info(f"   ✅ Product ID 매칭: {prod}")
        
        return match_vendor or match_item or match_product

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
                name = element.get_text(strip=True)
                logger.info(f"   📝 상품명 추출 성공 (선택자: {selector})")
                return name
        
        logger.warning(f"   ⚠️ 상품명 추출 실패 - 모든 선택자 실패")
        return "상품명 추출 실패"

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
