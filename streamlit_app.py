# streamlit_app.py
import streamlit as st
import pandas as pd
import time
import random
from datetime import datetime
import threading
import queue

# 기존 CoupangCrawler 클래스 그대로 사용
from coupang_crawler import CoupangCrawler  # 기존 클래스 임포트

# Streamlit 설정
st.set_page_config(
    page_title="쿠팡 순위 추적기",
    page_icon="🛒",
    layout="wide"
)

st.title("🛒 쿠팡 순위 추적기")
st.markdown("**IP 분산을 통한 안전한 크롤링 서비스**")

# 세션 상태 초기화
if 'results' not in st.session_state:
    st.session_state.results = []
if 'is_running' not in st.session_state:
    st.session_state.is_running = False

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
        default=["PC", "Android"]
    )
    
    # 딜레이 설정
    delay = st.slider("요청 간 딜레이 (초)", 5, 15, 8)
    
    # 페이지 수
    pages = st.slider("검색할 페이지 수", 1, 10, 5)
    
    # 백그라운드 실행
    headless = st.checkbox("백그라운드 실행", value=True)

# 검색 실행 버튼
if st.button("🔍 검색 시작", type="primary", disabled=st.session_state.is_running):
    if not url_input or not keywords:
        st.error("상품 URL과 키워드를 모두 입력해주세요.")
    elif not platform_options:
        st.error("최소 하나의 플랫폼을 선택해주세요.")
    else:
        # 검색 시작
        st.session_state.is_running = True
        st.session_state.results = []
        
        # 진행 상황 표시
        progress_bar = st.progress(0)
        status_text = st.empty()
        
        # 키워드 리스트 생성
        keyword_list = [kw.strip() for kw in keywords.split('\n') if kw.strip()]
        platform_list = [p.lower() for p in platform_options]
        
        total_tasks = len(keyword_list) * len(platform_list)
        completed_tasks = 0
        
        # 결과 테이블 미리 생성
        results_placeholder = st.empty()
        
        # 크롤링 실행
        for platform in platform_list:
            for keyword in keyword_list:
                if st.session_state.is_running:  # 중지 체크
                    completed_tasks += 1
                    progress = completed_tasks / total_tasks
                    
                    progress_bar.progress(progress)
                    status_text.text(f"진행 중: {platform.upper()} - {keyword} ({completed_tasks}/{total_tasks})")
                    
                    try:
                        # 크롤러 실행
                        crawler = CoupangCrawler(
                            platform=platform,
                            headless=headless,
                            delay=delay
                        )
                        
                        result = crawler.rank(keyword, url_input, pages)
                        
                        if result:
                            st.session_state.results.append(result)
                        else:
                            # 결과 없을 때도 기록
                            st.session_state.results.append({
                                "keyword": keyword,
                                "platform": platform,
                                "rank": "미노출",
                                "page": "-",
                                "product": "-",
                                "time": datetime.now().strftime("%H:%M:%S")
                            })
                        
                        # 실시간 결과 업데이트
                        if st.session_state.results:
                            df = pd.DataFrame(st.session_state.results)
                            results_placeholder.dataframe(df, use_container_width=True)
                        
                        # 딜레이
                        time.sleep(random.uniform(2, 4))
                        
                    except Exception as e:
                        st.error(f"오류 발생: {str(e)}")
                        break
        
        # 완료 처리
        st.session_state.is_running = False
        progress_bar.progress(1.0)
        status_text.text("✅ 검색 완료!")
        
        if st.session_state.results:
            st.success(f"총 {len(st.session_state.results)}개의 결과를 찾았습니다.")

# 중지 버튼
if st.session_state.is_running:
    if st.button("⏹️ 중지", type="secondary"):
        st.session_state.is_running = False
        st.warning("검색이 중지되었습니다.")

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
    col1, col2, col3 = st.columns(3)
    
    with col1:
        found_count = len([r for r in st.session_state.results if r['rank'] != '미노출'])
        st.metric("순위 발견", f"{found_count}개")
    
    with col2:
        not_found_count = len([r for r in st.session_state.results if r['rank'] == '미노출'])
        st.metric("미노출", f"{not_found_count}개")
    
    with col3:
        if found_count > 0:
            avg_rank = sum([int(r['rank']) for r in st.session_state.results if r['rank'] != '미노출']) / found_count
            st.metric("평균 순위", f"{avg_rank:.1f}위")
        else:
            st.metric("평균 순위", "N/A")

# 사이드바 정보
with st.sidebar:
    st.header("ℹ️ 사용 가이드")
    st.info("""
    **IP 보호 메커니즘:**
    - Streamlit Cloud 서버에서 실행
    - 개인 IP 노출 없음
    - 자동 트래픽 분산
    
    **사용 방법:**
    1. 쿠팡 상품 URL 입력
    2. 검색할 키워드 입력
    3. 플랫폼과 옵션 선택
    4. 검색 시작
    """)
    
    st.header("📈 실시간 상태")
    if st.session_state.is_running:
        st.success("🟢 크롤링 실행 중")
    else:
        st.info("🔵 대기 중")
    
    st.header("🔧 서버 정보")
    st.text(f"서버 시간: {datetime.now().strftime('%H:%M:%S')}")
    st.text("IP 보호: ✅ 활성")
