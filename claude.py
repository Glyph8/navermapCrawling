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
    
    def scroll_to_load_all_items(self, max_scrolls=4):
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
            print("search iframe으로 전환 성공")
        except Exception as e:
            print(f"search iframe 전환 실패: {e}")
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
        

        # 초기 항목 수 확인 (스크롤 진행 확인을 위한 지표)
        initial_items = self.driver.find_elements(By.CSS_SELECTOR, "li.UEzoS")
        initial_count = len(initial_items)
        print(f"초기 항목 수: {initial_count}")

        # 연속으로 높이가 변하지 않은 횟수를 추적
        unchanged_count = 0
        last_height = self.driver.execute_script("return arguments[0].scrollHeight", container)

        # 스크롤 수행
        for scroll in range(max_scrolls):
            print(f"스크롤 {scroll+1}/{max_scrolls} 수행 중...")

            # 컨테이너 끝까지 스크롤
            self.driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", container)
            time.sleep(3)  # 새 결과 로딩 대기

            # 새 높이 확인
            new_height = self.driver.execute_script("return arguments[0].scrollHeight", container)

            # 현재 항목 수 확인
            current_items = self.driver.find_elements(By.CSS_SELECTOR, "li.UEzoS")
            current_count = len(current_items)
            print(f"현재 항목 수: {current_count} (스크롤 {scroll+1}번 후)")

            # 항목 수 또는 높이를 기준으로 스크롤 진행 여부 판단
            if new_height == last_height:
                unchanged_count += 1
                print(f"높이 변화 없음 ({unchanged_count}번 연속)")
                
                # 높이가 3번 연속으로 변하지 않으면 추가 시도
                if unchanged_count >= 3:
                    # 특정 지점으로 스크롤 시도 (중간 지점으로)
                    mid_height = new_height / 2
                    self.driver.execute_script(f"arguments[0].scrollTo(0, {mid_height});", container)
                    time.sleep(1)
                    # 다시 맨 아래로 스크롤
                    self.driver.execute_script("arguments[0].scrollTo(0, arguments[0].scrollHeight);", container)
                    time.sleep(3)
                    
                    # 다시 확인
                    newer_height = self.driver.execute_script("return arguments[0].scrollHeight", container)
                    if newer_height == new_height and current_count == initial_count:
                        print("스크롤 진행이 멈춤, 모든 결과가 로드된 것으로 판단")
                        break
                    else:
                        # 높이가 변했거나 항목이 증가했으면 계속 진행
                        unchanged_count = 0
                        new_height = newer_height
            else:
                # 높이가 변했으면 카운터 리셋
                unchanged_count = 0
                
            # JavaScript 실행을 통한 직접 스크롤 시도 (대안적 방법)
            if scroll > 2 and current_count <= initial_count:
                print("직접 JavaScript 실행으로 스크롤 시도")
                self.driver.execute_script("""
                    document.querySelector('li.UEzoS:last-child').scrollIntoView({
                        behavior: 'smooth',
                        block: 'end'
                    });
                """)
                time.sleep(2)
                
            last_height = new_height
            
            # 항목이 증가했는지 확인
            if current_count > initial_count:
                initial_count = current_count
                print(f"새로운 항목이 로드됨 (총 {current_count}개)")
            else:
                print("새로운 항목이 로드되지 않음")
                
                # 같은 높이에서 항목이 2번 이상 증가하지 않으면 추가 시도
                if unchanged_count >= 2:
                    # 페이지 내 특정 버튼이 있는지 확인 (더보기 버튼 등)
                    try:
                        more_button = self.driver.find_element(By.CSS_SELECTOR, "button.more_btn")
                        more_button.click()
                        print("더보기 버튼 클릭")
                        time.sleep(3)
                        unchanged_count = 0
                    except:
                        pass
                    
        print(f"스크롤 완료. 총 {current_count}개의 항목 로드됨")

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
            fieldnames = ['장소 이름', '장소 카테고리', '장소 주소', '분위기', '인기토픽', '찾는목적', '인기연령10대', '인기연령20대','인기연령30대','인기연령40대','인기연령50대','인기연령60대', '인기성별']
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
                    # 현재 페이지가 iframe 내부인지 확인
                    is_inside_iframe = self.driver.execute_script("return window.self !== window.top")
                
                    if is_inside_iframe:
                        print("현재는 iframe 내부에 있습니다.")
                    else:
                        print("현재는 일반 페이지(iframe 외부)에 있습니다.")
                
                except Exception as e:
                    print("iframe 확인 중 오류 발생:", e)


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
                                # place_item.click()
                                text_element = place_item.find_element(By.TAG_NAME, "span")  # 텍스트가 있는 span 찾기
                                text_element.click()  # 텍스트 요소 클릭
                            except:
                                # 클릭이 안 되면 JavaScript로 클릭 시도
                                # self.driver.execute_script("arguments[0].click();", place_item)
                                self.driver.execute_script("arguments[0].click();", text_element)

                            time.sleep(4)  # 상세 정보 로딩 대기 시간 증가

                            # 상세 정보 수집
                            place_data = self.collect_place_info(region)
                            
                            # 지역이 일치하는 장소만 저장
                            if place_data:
                                writer.writerow(place_data)
                                total_places += 1
                            
                            # 리스트 화면으로 돌아가기
                            # self.driver.back()

                            # 다시 search iframe으로 전환
                            try:
                                iframe = self.driver.find_element(By.ID, "searchIframe")
                                self.driver.switch_to.frame(iframe)
                                print("search iframe으로 전환 성공")
                            except Exception as e:
                                print(f"search iframe 전환 실패: {e}")
                                return                            

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
        
        # 먼저 기본 문서로 돌아오기
        self.driver.switch_to.default_content()  

        #entry iframe으로 전환
        try:
            iframe = self.driver.find_element(By.ID, "entryIframe")
            self.driver.switch_to.frame(iframe)
            print("entry iframe으로 전환 성공")
        except Exception as e:
            print(f"entry iframe 전환 실패: {e}")
            return

        try:
            # 장소 이름 수집 - XPath 사용
            place_name = "정보 없음"
            xpath_selector = '//*[@id="_title"]/div/span[1]'
            
            try:
                name_element = self.driver.find_element(By.XPATH, xpath_selector)
                if name_element:
                    place_name = name_element.text.strip()
            except:
                pass        
            
            # 장소 카테고리 수집 - 여러 선택자 시도 //*[@id="_title"]/div/span[2]
            place_category = "정보 없음"
            category_xpath_selector = '//*[@id="_title"]/div/span[2]'

            try:
                category_element = self.driver.find_element(By.XPATH, category_xpath_selector)
                if category_element:
                    place_category = category_element.text.strip()
                    print(f"장소 카테고리 출력 : {place_category}")                    
            except:
                pass        
   
            # 장소 주소 수집 - 여러 선택자 시도
            try:
                # 장소 주소 수집 - XPath 사용
                place_address = "정보 없음"

                xpath_address = '//*[@id="app-root"]/div/div/div/div[5]/div/div[2]/div[1]/div/div[1]/div/a/span[1]'
                css_address = "#app-root > div > div > div > div:nth-child(5) > div > div:nth-child(2) > div.place_section_content > div > div.O8qbU.tQY7D > div > a > span.LDgIH"

                try:
                    print("주소 수집 xpath시도")
                    address_element = self.driver.find_element(By.XPATH, xpath_address)
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", address_element)

                    if address_element:
                        place_address = address_element.text.strip()
                        print("주소 출력:", place_address)
                except:
                    try:
                        # XPath 실패 시 CSS_SELECTOR 시도
                        print("주소 수집 css시도")
                        address_element = self.driver.find_element(By.CSS_SELECTOR, css_address)
                        place_address = address_element.text.strip()
                    except:
                        pass
                        
            except Exception as e:
                print(f"Error: {e}")
                return "정보 없음"            
                    
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
            
            # 데이터랩 항목까지 스크롤을 내려야 함!
            try:
                # 스크롤을 여러 번 내리면서 동적 요소 로딩을 유도
                scroll_attempts = 10  # 최대 10번 시도
                last_height = self.driver.execute_script("return document.body.scrollHeight")

                for _ in range(scroll_attempts):
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    time.sleep(1.5)  # AJAX 로딩을 기다리는 시간

                    new_height = self.driver.execute_script("return document.body.scrollHeight")
                    if new_height == last_height:
                        break  # 더 이상 스크롤이 변하지 않으면 중지
                    last_height = new_height

                # 데이터랩 더보기 버튼 찾기

                # 데이터랩 안보이는 경우 체크가 필요. 광고 항목에는 안뜨는 것 같기도? 없으면 넘겨야할듯
                time.sleep(1)
                datalab_detail_xpath = '//*[@id="app-root"]/div/div/div/div[6]/div/div[8]/div[2]/div/a'
                # datalab_datail_css = "app-root > div > div > div > div:nth-child(6) > div > div.place_section.I_y6k > div.NSTUp > div > a > span"
                datalab_datail_css = "span.fvwqf[6]"

                try:
                    datalab_detail_element = self.driver.find_element(By.XPATH, datalab_detail_xpath)
                    self.driver.execute_script("arguments[0].scrollIntoView(true);", datalab_detail_element)
                    time.sleep(0.5)  # 안정적인 클릭을 위해 대기
                    datalab_detail_element.click()
                except Exception as e:
                    try:
                        print("DataLab 더보기 버튼 XPath 실패, CSS_SELECTOR 시도")
                        datalab_datail_element = self.driver.find_elements(By.CLASS_NAME, "fvwqf")
                        if len(datalab_datail_element) >= 6: #데이터 랩 없는 경우 6개인듯?
                            target_element = datalab_datail_element[5]  # 6번째 요소
                            print("6번째 span 태그 내용:", target_element.text)
                            target_element.click()
                        else:
                            print("요소가 6개보다 적습니다.")   #데이터 랩 없는 경우? 있어도 이쪽으로 넘어가는데?
                        time.sleep(0.5)
                        print(f"요소 개수 : {len(datalab_datail_element)}")
                        for i in range(len(datalab_datail_element)):
                            print(f"{i}번 요소 : {datalab_datail_element[i]}")
                            print()
                            if datalab_datail_element[i].text.strip() == "더보기":
                                datalab_datail_element[i].click()
                                print(f"더보기와 일치한 {i}번째 요소 클릭시도했음")
                                break  # 클릭 후 루프 종료

                    except:
                        print("DataLab 데이터가 없는 경우로 판단, DataLab 정보 생략")
                        # 먼저 기본 문서로 돌아오기
                        self.driver.switch_to.default_content()  
                        place_data = {
                            '장소 이름': place_name,
                            '장소 카테고리': place_category,
                            '장소 주소': place_address,
                            '분위기': "정보 없음",
                            '인기토픽': "정보 없음",
                            '찾는목적': "정보 없음",
                            '인기연령10대': "정보 없음",
                            '인기연령20대': "정보 없음",
                            '인기연령30대': "정보 없음",
                            '인기연령40대': "정보 없음",
                            '인기연령50대': "정보 없음",
                            '인기연령60대': "정보 없음",
                            '인기성별': "정보 없음",
                        }
                        return place_data   
                        
                        
            except Exception as e:
                print(f"Error: {e}")
                return "정보 없음"        
            time.sleep(2) #DataLab 더보기 정보 로딩 대기

            # 분위기 수집 - 여러 방법 시도 (XPath와 CSS 선택자 모두 사용)
            atmosphere = "정보 없음"
            # //*[@id="app-root"]/div/div/div/div[6]/div/div[9]/div[1]/div[1]/div/ul/li[1]/span[2]
            try:
                # 방법 1: XPath로 라벨 뒤의 내용 찾기
                xpath_patterns = [
                    '//*[@id="app-root"]/div/div/div/div[6]/div/div[9]/div[1]/div[1]/div/ul/li[1]/span[2]',
                    "//div[contains(text(), '분위기')]/following-sibling::div",
                    "//span[contains(text(), '분위기')]/following-sibling::span",
                    "//span[contains(text(), '분위기')]/parent::*/following-sibling::*"
                ]
                
                for xpath in xpath_patterns:
                    try:
                        elements = self.driver.find_elements(By.XPATH, xpath)
                        if elements:
                            atmosphere = elements[0].text.strip()
                            print(f"분위기 출력: {atmosphere}")
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
            # //*[@id="app-root"]/div/div/div/div[6]/div/div[9]/div[1]/div[1]/div/ul/li[2]/span[2]
            popular_topics = "정보 없음"
            try:
                xpath_patterns = [
                    '//*[@id="app-root"]/div/div/div/div[6]/div/div[9]/div[1]/div[1]/div/ul/li[2]/span[2]',
                    "//div[contains(text(), '인기토픽')]/following-sibling::div",
                    "//span[contains(text(), '인기토픽')]/following-sibling::span",
                    "//span[contains(text(), '인기토픽')]/parent::*/following-sibling::*"
                ]
                
                for xpath in xpath_patterns:
                    try:
                        elements = self.driver.find_elements(By.XPATH, xpath)
                        if elements:
                            popular_topics = elements[0].text.strip()
                            print(f"인기토픽 출력 : {popular_topics}")
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
            # //*[@id="app-root"]/div/div/div/div[6]/div/div[9]/div[1]/div[1]/div/ul/li[3]/span[2]
            visit_purpose = "정보 없음"
            try:
                xpath_patterns = [
                    '//*[@id="app-root"]/div/div/div/div[6]/div/div[9]/div[1]/div[1]/div/ul/li[3]/span[2]',
                    "//div[contains(text(), '찾는목적')]/following-sibling::div",
                    "//span[contains(text(), '찾는목적')]/following-sibling::span",
                    "//span[contains(text(), '찾는목적')]/parent::*/following-sibling::*"
                ]
                
                for xpath in xpath_patterns:
                    try:
                        elements = self.driver.find_elements(By.XPATH, xpath)
                        if elements:
                            visit_purpose = elements[0].text.strip()
                            print(f"찾는목적 출력 : {visit_purpose}")
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

            # 연령대별 XPATH 및 CSS 선택자 매핑
            age_selectors = {
                "popular_age10": {
                    # "xpath": '//*[@id="bar_chart_container"]/ul/li[1]/div[1]/span/span[1]',
                    "xpath": '//*[@id="bar_chart_container"]/ul/li[1]/div[1]/span/span',
                    "css": "#bar_chart_container > ul > li:nth-child(1) > div.VIe0v > span > span:nth-child(1)"
                },
                "popular_age20": {
                    "xpath": '//*[@id="bar_chart_container"]/ul/li[2]/div[1]/span/span[1]',
                    # "xpath": '//*[@id="bar_chart_container"]/ul/li[2]/div[1]/span/span[1]',
                    "css": "#bar_chart_container > ul > li:nth-child(2) > div.VIe0v > span > span:nth-child(1)",
                    # "css": "#bar_chart_container > ul > li:nth-child(2) > div.VIe0v > span > span:nth-child(1)"
                },
                "popular_age30": {
                    "xpath": '//*[@id="bar_chart_container"]/ul/li[3]/div[1]/span/span[1]',
                    "css": "#bar_chart_container > ul > li:nth-child(3) > div.VIe0v > span > span:nth-child(1)"
                },
                "popular_age40": {
                    "xpath": '//*[@id="bar_chart_container"]/ul/li[4]/div[1]/span/span[1]',
                    "css": "#bar_chart_container > ul > li:nth-child(4) > div.VIe0v > span > span:nth-child(1)"
                },
                "popular_age50": {
                    "xpath": '//*[@id="bar_chart_container"]/ul/li[5]/div[1]/span/span[1]',
                    "css": "#bar_chart_container > ul > li:nth-child(5) > div.VIe0v > span > span:nth-child(1)"
                },
                "popular_age60": {
                    "xpath": '//*[@id="bar_chart_container"]/ul/li[6]/div[1]/span/span',
                    "css": "#bar_chart_container > ul > li:nth-child(6) > div.VIe0v > span > span"
                }
            }            
            # 연령별 변수 선언 및 데이터 할당
            popular_age10 = popular_age20 = popular_age30 = popular_age40 = popular_age50 = popular_age60 = "정보 없음"

            for age_group, selectors in age_selectors.items():
                try:
                    # 먼저 XPATH로 시도
                    age_element = self.driver.find_element(By.XPATH, selectors["xpath"])
                    age_value = age_element.text.strip()
                except:
                    try:
                        # XPATH 실패 시 CSS_SELECTOR 시도
                        age_element = self.driver.find_element(By.CSS_SELECTOR, selectors["css"])
                        age_value = age_element.text.strip()
                    except:
                        print(f"{age_group} 데이터를 찾을 수 없습니다.")
                        age_value = "정보 없음"

                # 변수에 값 저장
                if age_group == "popular_age10":
                    popular_age10 = age_value
                elif age_group == "popular_age20":
                    popular_age20 = age_value
                elif age_group == "popular_age30":
                    popular_age30 = age_value
                elif age_group == "popular_age40":
                    popular_age40 = age_value
                elif age_group == "popular_age50":
                    popular_age50 = age_value
                elif age_group == "popular_age60":
                    popular_age60 = age_value

            # 결과 출력
            print("10대:", popular_age10)
         
            # 인기성별 수집
            popular_gender = "정보 없음"
            
            # 선택자 리스트 (우선순위대로 시도)
            selectors = [
                (By.CSS_SELECTOR, "#_datalab_chart_donut1_0 > svg > g:nth-child(2) > g.c3-chart > g.c3-chart-arcs > g.c3-chart-arc.c3-target.c3-target-male > text:nth-child(3)"),
                (By.XPATH, '//*[@id="_datalab_chart_donut1_0"]/svg/g[1]/g[3]/g[4]/g[2]/text[2]'),
                (By.XPATH, '//*[@id="_datalab_chart_donut1_0"]/svg/g[1]/g[3]/g[4]/g[2]/text[1]'),
            ]

            # 변수 초기화
            male_text_value = "정보 없음"

            # 선택자 순차적으로 시도
            for by, selector in selectors:
                try:
                    print("성별 비율 선택자 접근 시행")
                    male_element = self.driver.find_element(by, selector)
                    male_text_value = male_element.text.strip()
                    break  # 성공하면 루프 탈출
                except:
                    continue  # 실패하면 다음 선택자로 시도
                
            # 결과 출력
            print("남자 성별비율 출력 :", male_text_value)
            popular_gender = male_text_value

            # 수집된 정보 반환
            place_data = {
                '장소 이름': place_name,
                '장소 카테고리': place_category,
                '장소 주소': place_address,
                '분위기': atmosphere.replace('\n', ' '),
                '인기토픽': popular_topics.replace('\n', ' '),
                '찾는목적': visit_purpose.replace('\n', ' '),
                '인기연령10대': popular_age10.replace('\n', ' '),
                '인기연령20대': popular_age20.replace('\n', ' '),
                '인기연령30대': popular_age30.replace('\n', ' '),
                '인기연령40대': popular_age40.replace('\n', ' '),
                '인기연령50대': popular_age50.replace('\n', ' '),
                '인기연령60대': popular_age60.replace('\n', ' '),
                '인기성별': popular_gender.replace('\n', ' '),
            }
            
            print(f"장소 '{place_name}' 정보 수집 완료")

            # 먼저 기본 문서로 돌아오기
            self.driver.switch_to.default_content()  

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
    regions = ["서울 광진구 중곡동", "서울 광진구 능동", "서울 광진구 구의동", 
              "서울 광진구 광장동", "서울 광진구 자양동", "서울 광진구 화양동", 
              "서울 광진구 군자동"]
    
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