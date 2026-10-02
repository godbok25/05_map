"""
노원구 공영주차장 주소 → 위도·경도 변환 (지오코딩)

입력 : nowon_parking.csv
출력 : nowon_parking_geocoded.csv  (위도·경도·좌표출처 열 채움)

엔진
  1) VWorld 지오코더 (국토교통부, 지번 주소 정확도 높음) — 환경변수 VWORLD_KEY가 있을 때 사용
     키 발급: https://www.vworld.kr  (오픈API > 인증키 발급, 무료)
  2) Nominatim (OpenStreetMap, 키 불필요) — 기본값
     지번 → 본번 → 동 단위 순으로 재시도하며, 동 단위 결과는 '근사'로 표시

실행 : pip install requests pandas
       python geocode.py                (Nominatim)
       VWORLD_KEY=발급키 python geocode.py  (VWorld 우선, 실패 시 Nominatim)
"""
import os, re, time
import pandas as pd
import requests

IN_CSV, OUT_CSV = "nowon_parking.csv", "nowon_parking_geocoded.csv"
VWORLD_KEY = os.environ.get("VWORLD_KEY", "")
UA = {"User-Agent": "nowon-parking-map/1.0 (data visualization coursework)"}
# 노원구 범위: 이 사각형 밖의 결과는 오탐으로 보고 버린다
BBOX = (37.600, 127.035, 37.700, 127.125)  # (남, 서, 북, 동)


def in_nowon(lat, lng):
    return BBOX[0] <= lat <= BBOX[2] and BBOX[1] <= lng <= BBOX[3]


def vworld(address):
    r = requests.get("https://api.vworld.kr/req/address", params={
        "service": "address", "request": "getcoord", "version": "2.0",
        "crs": "epsg:4326", "type": "PARCEL", "format": "json",
        "address": address, "key": VWORLD_KEY}, timeout=10).json()
    if r.get("response", {}).get("status") == "OK":
        p = r["response"]["result"]["point"]
        return float(p["y"]), float(p["x"])
    return None


def nominatim(q):
    r = requests.get("https://nominatim.openstreetmap.org/search", params={
        "q": q, "format": "json", "limit": 1, "countrycodes": "kr",
        "viewbox": f"{BBOX[1]},{BBOX[2]},{BBOX[3]},{BBOX[0]}", "bounded": 1},
        headers=UA, timeout=10).json()
    time.sleep(1.1)  # Nominatim 이용 정책: 초당 1회 이하
    return (float(r[0]["lat"]), float(r[0]["lon"])) if r else None


def geocode(address):
    # address 예: "서울특별시 노원구 상계동 693-5"
    m = re.search(r"노원구\s+(\S+동)\s+(\d+)(?:-(\d+))?", address)
    dong, main, sub = (m.group(1), m.group(2), m.group(3)) if m else ("", "", "")
    if VWORLD_KEY:
        hit = vworld(address)
        if hit and in_nowon(*hit):
            return hit, "지오코딩(VWorld·지번)"
    tries = []
    if m:
        lot = main if not sub or sub == "0" else f"{main}-{sub}"
        tries += [(f"서울특별시 노원구 {dong} {lot}", "지오코딩(OSM·지번)"),
                  (f"서울특별시 노원구 {dong} {main}", "지오코딩(OSM·본번)"),
                  (f"{dong}, 노원구, 서울특별시", "지오코딩(OSM·동 중심, 근사)")]
    for q, label in tries:
        hit = nominatim(q)
        if hit and in_nowon(*hit):
            return hit, label
    return None, "변환 실패"


df = pd.read_csv(IN_CSV, encoding="utf-8-sig")
for i, row in df.iterrows():
    if pd.notna(row["위도"]) and pd.notna(row["경도"]):
        continue  # 원본 데이터에 좌표가 있으면 유지
    hit, label = geocode(row["주소"])
    if hit:
        df.at[i, "위도"], df.at[i, "경도"] = round(hit[0], 6), round(hit[1], 6)
    df.at[i, "좌표출처"] = label
    print(f"{row['주차장명']:<22} {label}")

df.to_csv(OUT_CSV, index=False, encoding="utf-8-sig")
print(f"\n저장: {OUT_CSV}  (좌표 {df['위도'].notna().sum()}/{len(df)}건)")
