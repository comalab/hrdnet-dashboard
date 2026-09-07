import requests
import xml.etree.ElementTree as ET
import pandas as pd
from datetime import datetime, timedelta
import time

class HRDNetCrawler:
    """HRD-Net API를 이용한 훈련과정 정보 수집"""

    def __init__(self, auth_key):
        self.auth_key = auth_key
        self.base_url = "https://www.work24.go.kr/cm/openApi/call/hr/callOpenApiSvcInfo310L01.do"

    def get_training_courses(
        self,
        train_organ_name="",
        course_name="",
        area_code="26",
        start_date=None,
        end_date=None,
        page_size=100,
        progress_callback=None,
    ):
        if start_date is None:
            three_years_ago = datetime.now()
            start_date = three_years_ago.strftime("%Y%m%d")

        all_courses = []
        page_num = 1
        total_count = 0

        while True:
            params = {
                "authKey": self.auth_key,
                "returnType": "XML",
                "outType": "1",
                "pageNum": str(page_num),
                "pageSize": str(page_size),
                "srchTraStDt": start_date,
                "srchTraEndDt": end_date,
                "sort": "ASC",
                "sortCol": "2",
            }
            if area_code:
                params["srchTraArea1"] = area_code
            if train_organ_name:
                params["srchTraOrganNm"] = train_organ_name
            if course_name:
                params["srchTraProcessNm"] = course_name

            try:
                response = requests.get(self.base_url, params=params, timeout=30)
                response.raise_for_status()

                root = ET.fromstring(response.content)
                scn_cnt = root.find(".//scn_cnt")
                total_count = int(scn_cnt.text) if scn_cnt is not None else 0

                scn_list = root.findall(".//scn_list")
                if not scn_list:
                    break

                for course in scn_list:
                    course_data = {
                        "훈련기관명": self._get_text(course, "subTitle"),
                        "과정명": self._get_text(course, "title"),
                        "회차": self._get_text(course, "trprDegr"),
                        "훈련유형": self._get_text(course, "trainTarget"),
                        "훈련구분코드": self._get_text(course, "trainTargetCd"),
                        "NCS코드": self._get_text(course, "ncsCd"),
                        "훈련시작일": self._get_text(course, "traStartDate"),
                        "훈련종료일": self._get_text(course, "traEndDate"),
                        "수강비": self._get_text(course, "courseMan"),
                        "실제훈련비": self._get_text(course, "realMan"),
                        "정원": self._get_text(course, "yardMan"),
                        "수강신청인원": self._get_text(course, "regCourseMan"),
                        "주소": self._get_text(course, "address"),
                        "전화번호": self._get_text(course, "telNo"),
                        "만족도점수": self._get_text(course, "stdgScor"),
                        "과정링크": self._get_text(course, "titleLink"),
                    }
                    all_courses.append(course_data)

                if progress_callback:
                    progress_callback(len(all_courses), total_count, page_num)

                if len(all_courses) >= total_count or len(scn_list) < page_size:
                    break

                page_num += 1
                time.sleep(0.5)

            except requests.exceptions.RequestException as e:
                raise RuntimeError(f"API 호출 오류: {e}")
            except ET.ParseError as e:
                raise RuntimeError(f"XML 파싱 오류: {e}")

        return all_courses, total_count

    def _get_text(self, element, tag_name):
        tag = element.find(tag_name)
        return tag.text if tag is not None and tag.text else ""