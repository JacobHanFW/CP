# streamlit_app.py - 실시간 로그 표시 버전
import streamlit as st
import pandas as pd
import time
import random
import threading
import logging
import io
import sys
from datetime import datetime
from coupang_crawler import CoupangCrawler

# Streamlit 설정
st.set_page_config(
    page_title="쿠팡 순위 추적기",
    page_icon="🛒",
    layout="wide"
)

# 로그 캡처 설정
class StreamlitLogHandler(logging.Handler):
    def __init__(self):
        super().__init__()
        self.log_records = []
        
    def emit(self, record):
        log_entry = self.format(record)
        self.log_records.append({
            'time': datetime.now().strftime("%H:%M:%S"),
            'level': record.levelname,
            'message': log_entry
        })
        
    def get_logs(self):
        return self.log_records.copy()
        
    def clear_logs(self):
        self.log_records.clear()

# 전역 로그 핸들러
if 'log_handler' not in st.session_state:
    st.session_state.log_handler = StreamlitLogHandler()
    formatter = logging.Formatter('%(name)s - %(levelname)s - %(message)s')
    st.session_state.log_handler.setFormatter(formatter)
    
    # coupang_crawler 로거에 핸들러 추가
    crawler_logger = logging.getLogger('coupang_crawler')
    crawler_logger.addHandler(st.session_state.log_handler)
    crawler_logger.setLevel(logging.INFO)

# 메인 UI
st.title("🛒 쿠팡 순위 추적기")
st.markdown("**IP 분산을 통한 안전한 크롤링 서비스 (디버깅 강화 버전)**")

# 세션 상태 초기화
if 'results' not in st.session_state:
    st.session_state.results = []
if 'is_running' not in st.session_state:
    st.session_state.is_running = False
if 'current_logs' not in st.session_state:
    st.session_state.current_logs = []

# 메인 입력 섹션
col1, col2 = st.columns([2, 1])

with col1:
    st.subheader("📝 검색 설정")
    
    # 상품 URL 입력
    url_input = st.text_input(
        "상품 URL",
        placeholder="https://www.coupang.com/vp/products/1234567890",
        help="쿠팡 상품 페이지 URL을 입력하세요"
    )
    
    # 키워드 입력
    keywords = st.text_area(
        "검색 키워드 (줄바꿈으로 구분)",
        placeholder="수건\n타올\n베개",
        height=100,
        help="검색할 키워드를 줄바꿈으로 구분하여 입력하세요"
    )

with col2:
    st.subheader("⚙️ 크롤링 옵션")
    
    # 플랫폼 선택
    platform_options = st.multiselect(
        "플랫폼 선택",
        ["PC", "Android"],
        default=["PC"]
    )
    
    # 딜레이 설정
    delay = st.slider("요청 간 딜레이 (초)", 5, 15, 10)
    
    # 페이지 수
    pages = st.slider("검색할 페이지 수", 1, 10, 3)
    
    # 백그라운드 실행
    headless = st.checkbox("백그라운드 실행", value=True)
    
    # 디버깅 옵션
    debug_mode = st.checkbox("상세 디버깅 모드", value=True)

# 실시간 로그 표시 영역
if debug_mode:
    st.subheader("🔍 실시간 디버깅 로그")
    log_container = st.container()
    with log_container:
        log_placeholder = st.empty()

# 검색 실행 함수
def run_search():
    """검색 실행 함수"""
    keyword_list = [kw.strip() for kw in keywords.split('\n') if kw.strip()]
    platform_list = [p.lower() for p in platform_options]
    
    total_tasks = len(keyword_list) * len(platform_list)
    completed_tasks = 0
    
    for platform in platform_list:
        for keyword in keyword_list:
            if not st.session_state.is_running:
                break
                
            completed_tasks += 1
            
            # 현재 작업 상태 업데이트
            progress = completed_tasks / total_tasks
            st.session_state.progress_bar.progress(progress)
            st.session_state.status_text.text(
                f"진행 중: {platform.upper()} - {keyword} ({completed_tasks}/{total_tasks})"
            )
            
            # 로그 초기화
            st.session_state.log_handler.clear_logs()
            
            try:
                # 크롤러 실행
                crawler = CoupangCrawler(
                    platform=platform,
                    headless=headless,
                    delay=delay
                )
                
                result = crawler.rank(keyword, url_input, pages)
                
                # 결과 처리
                if result:
                    st.session_state.results.append(result)
                    st.session_state.status_text.text(
                        f"✅ {keyword}: {result['rank']}위 발견!"
                    )
                else:
                    st.session_state.results.append({
                        "keyword": keyword,
                        "platform": platform,
                        "rank": "미노출",
                        "page": "-",
                        "product": "-",
                        "time": datetime.now().strftime("%H:%M:%S")
                    })
                    st.session_state.status_text.text(
                        f"❌ {keyword}: 순위 없음"
                    )
                
                # 실시간 결과 업데이트
                if st.session_state.results:
                    df = pd.DataFrame(st.session_state.results)
                    st.session_state.results_placeholder.dataframe(df, use_container_width=True)
                
                # 딜레이
                time.sleep(random.uniform(2, 4))
                
            except Exception as e:
                error_msg = f"오류 발생 ({keyword}): {str(e)}"
                st.session_state.status_text.text(error_msg)
                st.error(error_msg)
    
    # 완료 처리
    st.session_state.is_running = False
    st.session_state.progress_bar.progress(1.0)
    st.session_state.status_text.text("✅ 검색 완료!")

# 검색 시작 버튼
if st.button("🔍 검색 시작", type="primary", disabled=st.session_state.is_running):
    if not url_input or not keywords:
        st.error("상품 URL과 키워드를 모두 입력해주세요.")
    elif not platform_options:
        st.error("최소 하나의 플랫폼을 선택해주세요.")
    else:
        # 검색 시작
        st.session_state.is_running = True
        st.session_state.results = []
        
        # UI 요소들 생성
        st.session_state.progress_bar = st.progress(0)
        st.session_state.status_text = st.empty()
        st.session_state.results_placeholder = st.empty()
        
        # 별도 스레드에서 검색 실행
        search_thread = threading.Thread(target=run_search, daemon=True)
        search_thread.start()

# 중지 버튼
if st.session_state.is_running:
    if st.button("⏹️ 중지", type="secondary"):
        st.session_state.is_running = False
        st.warning("검색이 중지되었습니다.")

# 실시간 로그 업데이트
if debug_mode and st.session_state.is_running:
    current_logs = st.session_state.log_handler.get_logs()
    
    if current_logs:
        # 최근 로그부터 표시
        log_text = ""
        for log_entry in current_logs[-50:]:  # 최근 50개만 표시
            level_emoji = {
                'INFO': 'ℹ️',
                'WARNING': '⚠️',
                'ERROR': '❌',
                'DEBUG': '🔧'
            }.get(log_entry['level'], '📝')
            
            log_text += f"{log_entry['time']} {level_emoji} {log_entry['message']}\n"
        
        with log_placeholder.container():
            st.text_area(
                "실시간 로그", 
                value=log_text, 
                height=300, 
                key=f"log_area_{len(current_logs)}"
            )

# 결과 표시
if st.session_state.results:
    st.subheader("📊 검색 결과")
    
    # 데이터프레임으로 변환
    df = pd.DataFrame(st.session_state.results)
    
    # 결과 테이블 표시
    st.dataframe(df, use_container_width=True)
    
    # 결과 다운로드
    csv = df.to_csv(index=False, encoding='utf-8-sig')
    st.download_button(
        label="📥 결과 CSV로 다운로드",
        data=csv,
        file_name=f"coupang_rank_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv",
        mime="text/csv"
    )
    
    # 통계 정보
    col1, col2, col3, col4 = st.columns(4)
    
    with col1:
        found_count = len([r for r in st.session_state.results if r['rank'] != '미노출'])
        st.metric("순위 발견", f"{found_count}개")
    
    with col2:
        not_found_count = len([r for r in st.session_state.results if r['rank'] == '미노출'])
        st.metric("미노출", f"{not_found_count}개")
    
    with col3:
        if found_count > 0:
            valid_ranks = [int(r['rank']) for r in st.session_state.results if r['rank'] != '미노출']
            avg_rank = sum(valid_ranks) / len(valid_ranks)
            st.metric("평균 순위", f"{avg_rank:.1f}위")
        else:
            st.metric("평균 순위", "N/A")
    
    with col4:
        total_searches = len(st.session_state.results)
        success_rate = (found_count / total_searches * 100) if total_searches > 0 else 0
        st.metric("성공률", f"{success_rate:.1f}%")

# 사이드바 정보
with st.sidebar:
    st.header("ℹ️ 사용 가이드")
    st.info("""
    **IP 보호 메커니즘:**
    - Streamlit Cloud 서버에서 실행
    - 개인 IP 노출 없음
    - 자동 트래픽 분산
    
    **디버깅 기능:**
    - 실시간 로그 표시
    - 스크린샷 자동 저장
    - 상세 진행 상황 추적
    """)
    
    st.header("📈 실시간 상태")
    if st.session_state.is_running:
        st.success("🟢 크롤링 실행 중")
    else:
        st.info("🔵 대기 중")
    
    st.header("🔧 디버깅 정보")
    st.text(f"서버 시간: {datetime.now().strftime('%H:%M:%S')}")
    st.text("IP 보호: ✅ 활성")
    st.text("로그 레벨: INFO")
    st.text("스크린샷: ✅ 활성")
    
    if st.session_state.results:
        st.header("📊 실행 통계")
        total_searches = len(st.session_state.results)
        found_count = len([r for r in st.session_state.results if r['rank'] != '미노출'])
        st.text(f"총 검색: {total_searches}개")
        st.text(f"순위 발견: {found_count}개")
        
        if total_searches > 0:
            success_rate = (found_count / total_searches * 100)
            st.text(f"성공률: {success_rate:.1f}%")

# 하단 디버깅 정보
if debug_mode and st.session_state.results:
    with st.expander("🔍 상세 디버깅 정보"):
        st.write("**검색 환경:**")
        st.write(f"- 서버: Streamlit Cloud")
        st.write(f"- 헤드리스 모드: {headless}")
        st.write(f"- 딜레이 설정: {delay}초")
        st.write(f"- 검색 페이지: {pages}페이지")
        
        # 실패한 검색 분석
        failed_searches = [r for r in st.session_state.results if r['rank'] == '미노출']
        if failed_searches:
            st.write(f"**미노출 키워드 분석 ({len(failed_searches)}개):**")
            for fail in failed_searches:
                st.write(f"- {fail['keyword']} ({fail['platform']})")
        
        # 성공한 검색 분석
        success_searches = [r for r in st.session_state.results if r['rank'] != '미노출']
        if success_searches:
            st.write(f"**순위 발견 키워드 ({len(success_searches)}개):**")
            for success in success_searches:
                st.write(f"- {success['keyword']}: {success['rank']}위 ({success['platform']})")
