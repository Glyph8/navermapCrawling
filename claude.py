from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
from webdriver_manager.chrome import ChromeDriverManager
import time
import csv
import re
import os
from datetime import datetime
import pandas as pd

class NaverMapCrawler:
    def __init__(self):
        """
        네이버 지도 크롤러 초기화
        - Chrome 웹드라이버 설정
        - 결과 저장 디렉토리 생성
        """
        # Chrome 옵션 설정
        chrome_options = Options()
        # 필요에 따라 headless 모드 설정 (주석 해제 시 브라우저 창이 뜨지 않음)
        # chrome_options.add_argument('--headless')
        chrome_options.add_argument('--no-sandbox')
        chrome_options.add_argument('--disable-dev-shm-usage')
        chrome_options.add_argument('--disable-gpu')  # GPU 가속 비활성화 (하드웨어 오류 방지)
        chrome_options.add_argument('--window-size=1920,1080')
        chrome_options.add_argument('--ignore-certificate-errors')  # 인증서 오류 무시
        chrome_options.add_argument('--disable-extensions')  # 확장 프로그램 비활성화
        chrome_options.add_argument('--disable-software-rasterizer')  # 소프트웨어 래스터라이저 비활성화
        
        # 웹드라이버 설정 - 예외 처리 추가
        try:
            self.driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=chrome_options)
        except Exception as e:
            print(f"ChromeDriver 설치 실패: {e}")
            print("대체 방법으로 시도합니다...")
            # 대체 방법: 로컬에 있는 Chrome 드라이버 사용
            try:
                self.driver = webdriver.Chrome(options=chrome_options)
            except Exception as e2:
                print(f"로컬 ChromeDriver 사용 실패: {e2}")
                raise Exception("웹드라이버를 초기화할 수 없습니다. Chrome과 ChromeDriver가 설치되어 있는지 확인하세요.")
        
        self.wait = WebDriverWait(self.driver, 15)  # 타임아웃 시간 15초로 증가
        
        # 결과 저장 디렉토리 생성
        self.results_dir = 'naver_map_results'
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)
        
        # 현재 시간을 파일명에 사용
        self.timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    def scroll_to_load_all_items(self, max_scrolls=10):
        """
        iframe 내부의 모든 검색 결과를 로드하기 위해 스크롤 다운 수행

        Args:
            max_scrolls (int): 최대 스크롤 시도 횟수
        """
        print("iframe으로 전환 후 스크롤을 내려 모든 검색 결과 로드 중...")

        # 먼저 iframe으로 전환
        try:
            iframe = self.driver.find_element(By.ID, "searchIframe")
            self.driver.switch_to.frame(iframe)
            print("iframe으로 전환 성공")
        except Exception as e:
            print(f"iframe 전환 실패: {e}")
            return

        # iframe 내부에서 컨테이너 찾기 - 먼저 XPATH 시도
        container = None
        try:
            container = self.driver.find_element(By.CSS_SELECTOR, 'div#_pcmap_list_scroll_container')
            print("CSS 선택자를 사용하여 컨테이너를 찾았습니다.")
        except:
            print("CSS 선택자로도 컨테이너를 찾을 수 없습니다.")

        if not container:
            print("스크롤 컨테이너를 찾을 수 없습니다.")
            # 기본 컨텍스트로 돌아가기
            self.driver.switch_to.default_content()
            return

        last_height = self.driver.execute_script("return arguments[0].scrollHeight", container)

        # 스크롤 수행
        for scroll in range(max_scrolls):
            print(f"스크롤 {scroll+1}/{max_scrolls} 수행 중...")

            # 컨테이너 끝까지 스크롤
            self.driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", container)
            time.sleep(2)  # 새 결과 로딩 대기

            # 새 높이 확인
            new_height = self.driver.execute_script("return arguments[0].scrollHeight", container)

            # 이미 모든 항목이 로드된 경우
            if new_height == last_height:
                print(f"모든 결과 로드됨 (스크롤 {scroll+1}번 후)")
                break

            last_height = new_height

        # 스크롤 작업 완료 후 기본 컨텍스트로 돌아가기
        # self.driver.switch_to.default_content()
        # print("기본 컨텍스트로 복귀")    


    def search_places(self, region, category):
        """
        네이버 지도에서 지역과 카테고리로 장소 검색
        
        Args:
            region (str): 검색할 행정구역 이름
            category (str): 검색할 장소 카테고리
        """
        # 네이버 지도 접속
        try:
            self.driver.get('https://map.naver.com/')
            time.sleep(3)  # 로딩 시간 증가
        except Exception as e:
            print(f"네이버 지도 접속 실패: {e}")
            return 0
        
        # 검색어 입력
        search_query = f"{region} {category}"
        print(f"검색어: {search_query}")
        
        try:
            # 검색창 요소 찾기 - 여러 선택자 시도
            search_box = None
            selectors = [
                "input.input_search", 
                "input.tEeEW", 
                "input[placeholder='장소, 주소 검색']",  # [사용자 편집 가능 - 1] 검색창 선택자를 네이버 지도 UI에 맞게 수정
                "input[title='검색어 입력']"
            ]
            
            for selector in selectors:
                try:
                    search_box = self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                    if search_box:
                        break
                except:
                    continue
            
            if not search_box:
                raise Exception("검색창을 찾을 수 없습니다")
                
            search_box.clear()
            search_box.send_keys(search_query)
            
            # 엔터키로 검색
            from selenium.webdriver.common.keys import Keys
            search_box.send_keys(Keys.RETURN)
  
        except Exception as e:
            print(f"검색 시도 중 오류: {e}")
            return 0
        
        # 검색 결과 로딩 대기
        time.sleep(5)  # 로딩 시간 증가
        
        # CSV 파일 생성
        filename = f"{self.results_dir}/{region.replace(' ', '_')}_{category}_{self.timestamp}.csv"
        with open(filename, 'w', newline='', encoding='utf-8-sig') as csvfile:
            fieldnames = ['장소 이름', '장소 카테고리', '장소 설명', '장소 주소', '분위기', '인기토픽', '찾는목적', '인기연령', '인기성별']
            writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
            writer.writeheader()
            
            # 페이지 순회
            page_num = 1
            total_places = 0
            
            while True:
                print(f"페이지 {page_num} 크롤링 중...")
                self.scroll_to_load_all_items()
                # 현재 페이지의 장소 목록 가져오기
                try:
                    # 검색 결과 항목들이 로드될 때까지 대기 - 여러 선택자 시도
                    place_items = None
                    item_selectors = [
                        "li.UEzoS.rTjJo",
                        "li.UEzoS", 
                        "li.rTjJo",  # [사용자 편집 가능 - 3] 검색 결과 항목 선택자를 네이버 지도 UI에 맞게 수정
                        "div#_pcmap_list_scroll_container"
                    ]
                    
                    
                    for selector in item_selectors:
                        try:
                            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                            place_items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                            if place_items:
                                break
                        except:
                            continue
                    
                    if not place_items:
                        print("이 페이지에 장소가 없거나 선택자가 일치하지 않습니다. 크롤링 종료.")
                        break
                    
                    # 각 장소 항목 순회
                    for idx, place_item in enumerate(place_items):
                        try:
                            # 장소 항목 클릭
                            print(f"장소 {idx+1}/{len(place_items)} 정보 수집 중...")
                            
                            # 스크롤해서 항목이 보이게 만들기
                            self.driver.execute_script("arguments[0].scrollIntoView(true);", place_item)
                            time.sleep(1)  # 스크롤 대기 시간 증가

                            # 항목 클릭
                            try:
                                place_item.click()
                            except:
                                # 클릭이 안 되면 JavaScript로 클릭 시도
                                self.driver.execute_script("arguments[0].click();", place_item)

                            time.sleep(3)  # 상세 정보 로딩 대기 시간 증가
                            
                            # 상세 정보 수집
                            place_data = self.collect_place_info(region)
                            
                            # 지역이 일치하는 장소만 저장
                            if place_data:
                                writer.writerow(place_data)
                                total_places += 1
                            
                            # 리스트 화면으로 돌아가기
                            self.driver.back()
                            time.sleep(3)  # 뒤로가기 후 대기 시간 증가
                            
                            # 검색 결과 재로딩 대기
                            for selector in item_selectors:
                                try:
                                    self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                                    place_items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                    if place_items:
                                        break
                                except:
                                    continue
                            
                        except (TimeoutException, NoSuchElementException, StaleElementReferenceException) as e:
                            print(f"장소 정보 수집 중 오류 발생: {e}")
                            # 오류 발생 시 리스트 화면으로 돌아가서 계속 진행
                            try:
                                self.driver.back()
                                time.sleep(3)
                                for selector in item_selectors:
                                    try:
                                        self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                                        place_items = self.driver.find_elements(By.CSS_SELECTOR, selector)
                                        if place_items:
                                            break
                                    except:
                                        continue
                            except:
                                print("검색 결과 화면으로 복귀 실패, 다음 지역/카테고리로 넘어갑니다.")
                                return total_places               
                    
                    # 다음 페이지 존재 여부 확인 및 이동
                    try:
                        next_button = None

                        # "다음페이지" 텍스트를 가진 span 태그 찾기
                        try:
                            next_button = self.driver.find_element(By.XPATH, "//span[@class='place_blind' and text()='다음페이지']")
                        except:
                            print("다음 페이지 버튼을 찾을 수 없습니다.")
                            break
                        
                        # page_num이 5이면 마지막 페이지로 판단하고 종료
                        if page_num >= 5:
                            print("마지막 페이지입니다.")
                                    # 스크롤 작업 완료 후 기본 컨텍스트로 돌아가기
                            self.driver.switch_to.default_content()
                            print("기본 컨텍스트로 복귀")    
                            break
                        
                        # 버튼 클릭 후 다음 페이지로 이동
                        next_button.click()
                        time.sleep(3)  # 페이지 전환 대기 시간 증가
                        page_num += 1  # 페이지 번호 증가

                    except Exception as e:
                        print(f"다음 페이지 이동 중 오류: {e}")
                        break                    

                except Exception as e:
                    print(f"페이지 크롤링 중 오류 발생: {e}")
                    break
            
            print(f"{region} {category} 크롤링 완료: {total_places}개 장소 수집")
            return total_places
    
    def collect_place_info(self, target_region):
        """
        개별 장소의 상세 정보 수집
        
        Args:
            target_region (str): 대상 행정구역 이름
            
        Returns:
            dict: 수집된 장소 정보
        """
        try:
            # 장소 이름 수집 - 여러 선택자 시도
            place_name = "정보 없음"
            name_selectors = [
                "span.GHAhO", # [사용자 편집 가능 - 6] 장소 이름 선택자를 네이버 지도 UI에 맞게 수정
                # "span.title_name", 
            ]
            
            for selector in name_selectors:
                try:
                    name_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if name_element:
                        place_name = name_element.text.strip()
                        break
                except:
                    continue
            
            # 장소 카테고리 수집 - 여러 선택자 시도
            place_category = "정보 없음"
            category_selectors = [
                # "span.category", 
                "span.lnJFt", # [사용자 편집 가능 - 7] 장소 카테고리 선택자를 네이버 지도 UI에 맞게 수정
                # "div.place_category"
            ]
            
            for selector in category_selectors:
                try:
                    category_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if category_element:
                        place_category = category_element.text.strip()
                        break
                except:
                    continue
            
            # 장소 설명 수집 - 여러 선택자 시도
            place_description = "정보 없음"
            desc_selectors = [
                # "div.place_section_content", 
                "div.XtBbS", # [사용자 편집 가능 - 8] 장소 설명 선택자를 네이버 지도 UI에 맞게 수정
                # "div.place_detail"
            ]
            
            for selector in desc_selectors:
                try:
                    desc_element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if desc_element:
                        place_description = desc_element.text.strip()
                        break
                except:
                    continue
            
            # 장소 주소 수집 - 여러 선택자 시도
            place_address = "정보 없음"
            address_selectors = [
                # "span.addr", 
                "span.LDgIH", 
                # "div.IhAeL",  # [사용자 편집 가능 - 9] 장소 주소 선택자를 네이버 지도 UI에 맞게 수정
                # "div.place_address"
            ]
            
            for selector in address_selectors:
                try:
                    address_elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    if address_elements:
                        place_address = address_elements[0].text.strip()
                        break
                except:
                    continue
            
            # 주소에 대상 지역이 포함되어 있는지 확인
            region_keywords = target_region.split()
            region_match = False
            
            # 주소에 지역명이 포함되어 있는지 확인 (보다 유연한 확인)
            for keyword in region_keywords[:2]:  # 첫 두 단어만 확인 (예: "서울시 광진구")
                if keyword in place_address:
                    region_match = True
                    break
            
            if not region_match:
                print(f"장소 '{place_name}'의 주소({place_address})가 대상 지역({target_region})에 포함되지 않아 건너뜁니다.")
                return None
            

            # 데이터랩 더보기 클릭
            try:
                while True:
                    # "더보기" 텍스트가 포함된 span 태그 찾기
                    more_span = self.driver.find_element(By.XPATH, "//span[contains(text(), '더보기')]")

                    # 요소가 보이면 클릭
                    if more_span.is_displayed():
                        more_span.click()
                        time.sleep(2)  # 데이터 로딩 대기
                    else:
                        break  # 요소가 없으면 종료
                    
            except Exception as e:
                print("더보기 클릭 중 오류 발생:", e)                           

            # 분위기 수집 - 여러 방법 시도 (XPath와 CSS 선택자 모두 사용)
            atmosphere = "정보 없음"
            try:
                # 방법 1: XPath로 라벨 뒤의 내용 찾기
                xpath_patterns = [
                    "//div[contains(text(), '분위기')]/following-sibling::div",
                    "//span[contains(text(), '분위기')]/following-sibling::span",
                    "//span[contains(text(), '분위기')]/parent::*/following-sibling::*"
                ]
                
                for xpath in xpath_patterns:
                    try:
                        elements = self.driver.find_elements(By.XPATH, xpath)
                        if elements:
                            atmosphere = elements[0].text.strip()
                            break
                    except:
                        continue
                
                # 방법 2: 컨테이너 내에서 키워드 검색
                if atmosphere == "정보 없음":
                    containers = self.driver.find_elements(By.CSS_SELECTOR, "div.sJgQj")  # [사용자 편집 가능 - 11]
                    for container in containers:
                        if "분위기" in container.text:
                            atmosphere = container.text.replace("분위기", "").strip()
                            break
            except:
                pass
            
            # 인기토픽 수집
            popular_topics = "정보 없음"
            try:
                xpath_patterns = [
                    "//div[contains(text(), '인기토픽')]/following-sibling::div",
                    "//span[contains(text(), '인기토픽')]/following-sibling::span",
                    "//span[contains(text(), '인기토픽')]/parent::*/following-sibling::*"
                ]
                
                for xpath in xpath_patterns:
                    try:
                        elements = self.driver.find_elements(By.XPATH, xpath)
                        if elements:
                            popular_topics = elements[0].text.strip()
                            break
                    except:
                        continue
                
                if popular_topics == "정보 없음":
                    containers = self.driver.find_elements(By.CSS_SELECTOR, "div.sJgQj")  # [사용자 편집 가능 - 12]
                    for container in containers:
                        if "인기토픽" in container.text:
                            popular_topics = container.text.replace("인기토픽", "").strip()
                            break
            except:
                pass
            
            # 찾는목적 수집
            visit_purpose = "정보 없음"
            try:
                xpath_patterns = [
                    "//div[contains(text(), '찾는목적')]/following-sibling::div",
                    "//span[contains(text(), '찾는목적')]/following-sibling::span",
                    "//span[contains(text(), '찾는목적')]/parent::*/following-sibling::*"
                ]
                
                for xpath in xpath_patterns:
                    try:
                        elements = self.driver.find_elements(By.XPATH, xpath)
                        if elements:
                            visit_purpose = elements[0].text.strip()
                            break
                    except:
                        continue
                
                if visit_purpose == "정보 없음":
                    containers = self.driver.find_elements(By.CSS_SELECTOR, "div.sJgQj")  # [사용자 편집 가능 - 13]
                    for container in containers:
                        if "찾는목적" in container.text:
                            visit_purpose = container.text.replace("찾는목적", "").strip()
                            break
            except:
                pass
            
            # 인기연령 수집
            popular_age = "정보 없음"            
            try:
                # 모든 '인기순위' 텍스트가 포함된 span 태그 찾기
                ranking_spans = driver.find_elements(By.XPATH, "//span[contains(text(), '인기순위')]")

                for rank_span in ranking_spans:
                    # 해당 span 태그가 포함된 부모 요소 찾기
                    parent_div = rank_span.find_element(By.XPATH, "./parent::div")

                    # 부모 요소 내에서 '1'과 '위'를 포함하는 span이 있는지 확인
                    one_span = parent_div.find_elements(By.XPATH, ".//span[text()='1']")
                    rank_word_span = parent_div.find_elements(By.XPATH, ".//span[text()='위']")

                    # '1'과 '위'가 존재하면 인기순위 1위 데이터로 간주
                    if one_span and rank_word_span:
                        try:
                            # 부모 요소 내부의 첫 번째 수치값(span.place_blind) 찾기
                            value_span = parent_div.find_element(By.XPATH, ".//span[contains(@class, 'place_blind')]")
                            value_text = value_span.text.strip()  # 숫자값 (예: 36.625%)

                            # 부모 요소 내에서 연령대 정보 찾기 (숫자값 다음 위치)
                            age_group_span = parent_div.find_element(By.XPATH, "./following-sibling::div")
                            age_group_text = age_group_span.text.strip()  # 연령대 (예: "10대")

                            # 최종 데이터 저장 (예: "36.625%_10대")
                            popular_age = (f"{value_text}_{age_group_text}")

                        except Exception as e:
                            print("수치 또는 연령대 추출 오류:", e)

            except Exception as e:
                print("데이터 추출 중 오류 발생:", e)


            # 인기성별 수집
            popular_gender = "정보 없음"
            try:
                # 첫 번째 '<tspan class="datalab-unit">%</tspan>' 요소 찾기
                first_percent = driver.find_element(By.XPATH, "(//tspan[@class='datalab-unit' and text()='%'])[1]")
            
                # 첫 번째 '%'의 부모 요소 찾기
                parent_element = first_percent.find_element(By.XPATH, "./parent::*")
            
                # 부모 요소 내부에서 '%' 앞의 텍스트 추출
                text_before_percent = parent_element.text.replace("%", "").strip()
                popular_gender = text_before_percent
       
                # xpath_patterns = [
                #     "//tspan[@class='datalab-unit' and text()='%']"
                # ]           
                # for xpath in xpath_patterns:
                #     try:
                #         elements = self.driver.find_elements(By.XPATH, xpath)
                #         if elements:
                #             popular_gender = elements[0].text.strip()
                #             break
                #     except:
                #         continue
                # if popular_gender == "정보 없음":
                #     containers = self.driver.find_elements(By.CSS_SELECTOR, "div.place_section, div.C6RjW, div.iwXlS")  # [사용자 편집 가능 - 15]
                #     for container in containers:
                #         if "인기성별" in container.text:
                #             popular_gender = container.text.replace("인기성별", "").strip()
                #             break
            except:
                pass
            

            # 수집된 정보 반환
            place_data = {
                '장소 이름': place_name,
                '장소 카테고리': place_category,
                '장소 설명': place_description.replace('\n', ' '),
                '장소 주소': place_address,
                '분위기': atmosphere.replace('\n', ' '),
                '인기토픽': popular_topics.replace('\n', ' '),
                '찾는목적': visit_purpose.replace('\n', ' '),
                '인기연령': popular_age.replace('\n', ' '),
                '인기성별': popular_gender.replace('\n', ' '),
            }
            
            print(f"장소 '{place_name}' 정보 수집 완료")
            return place_data
            
        except Exception as e:
            print(f"장소 정보 수집 중 예외 발생: {e}")
            return None
    
    def run(self, regions, categories):
        """
        주어진 지역과 카테고리에 대한 크롤링 실행
        
        Args:
            regions (list): 크롤링할 행정구역 리스트
            categories (list): 크롤링할 카테고리 리스트
        """
        total_results = {}
        
        # 결과 저장을 위한 데이터프레임 초기화
        results_df = pd.DataFrame(columns=['지역', '카테고리', '수집된 장소 수'])
        
        for region in regions:
            for category in categories:
                print(f"\n{'='*50}")
                print(f"{region} - {category} 크롤링 시작")
                print(f"{'='*50}")
                
                try:
                    # 장소 검색 및 정보 수집
                    count = self.search_places(region, category)
                    
                    # 결과 저장
                    results_df = pd.concat([results_df, pd.DataFrame({
                        '지역': [region],
                        '카테고리': [category],
                        '수집된 장소 수': [count]
                    })])
                    
                    # 중간 결과 저장
                    results_df.to_csv(f"{self.results_dir}/수집_결과_요약_{self.timestamp}.csv", index=False, encoding='utf-8-sig')
                    
                    print(f"\n{region} - {category} 크롤링 완료: {count}개 장소 수집")
                except Exception as e:
                    print(f"{region} - {category} 크롤링 중 오류 발생: {e}")
                    results_df = pd.concat([results_df, pd.DataFrame({
                        '지역': [region],
                        '카테고리': [category],
                        '수집된 장소 수': [0]
                    })])
                    results_df.to_csv(f"{self.results_dir}/수집_결과_요약_{self.timestamp}.csv", index=False, encoding='utf-8-sig')
        
                    print(f"\n{region} - {category} 크롤링 완료: {count}개 장소 수집")
        
        # 결과 출력
        print("\n======= 크롤링 최종 결과 =======")
        print(results_df)
        print(f"결과 파일은 '{self.results_dir}' 디렉토리에 저장되었습니다.")
    
    def close(self):
        """
        크롤러 종료 및 리소스 해제
        """
        self.driver.quit()


# 메인 실행 코드
if __name__ == "__main__":
    # 크롤링할 지역 리스트
    regions = ["서울시 광진구 중곡동", "서울시 광진구 능동", "서울시 광진구 구의동", 
              "서울시 광진구 광장동", "서울시 광진구 자양동", "서울시 광진구 화양동", 
              "서울시 광진구 군자동"]
    
    # 크롤링할 카테고리 리스트
    categories = ["카페", "스터디카페", "보드게임카페", 
                 "영화관", "공원","스포츠시설"]
    
    # 크롤러 생성 및 실행
    crawler = NaverMapCrawler()
    
    try:
        # 크롤링 실행
        crawler.run(regions, categories)
    except Exception as e:
        print(f"크롤링 중 오류 발생: {e}")
    finally:
        # 크롤러 종료
        crawler.close()