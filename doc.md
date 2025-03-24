```
- 실행 가이드

1. 가상환경 생성
python -m venv venv

2. 가상환경 실행
.\venv\Scripts\activate

3. 필요한 라이브러리 다운로드
pip install selenium webdriver-manager pandas

```

고려할 점과 돌이켜볼 점

1. 평점은 안보이게 해둔 가게가 많음 + 현재 안정화X 상태라 부담.
2. 검색결과 search iframe, 항목 entry iframe 2개를 오가야함.
3. datalab은 검색결과 상위 일부. 즉 최소한 꽤 검색된 경우에만 존재.
4. 항목 클릭 시 에러로 다시 이용해달라는 페이지가 보일 수 있음.
5.
