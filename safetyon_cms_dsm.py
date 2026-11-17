# -*- coding: utf-8 -*-
"""
주식회사 세이프티온 (SafetyON Inc.)
5채널 올인원 스마트 전자식 디지털 룸미러 (CMS & DSM Simulator)
특허 제24호 기반 통합 전장 시스템 시뮬레이터

[대표님 요청사항 100% 완벽 반영 Ver 3.3]
1. 안내 멘트 이상 현상(늘어짐, 에코, 겹침) 100% 완전 해결:
   - 정확한 44100Hz 고음질 리샘플링 적용 (늘어짐/괴물 목소리 완전 박멸)
   - 단일 채널 무결점 음성 출력(_play_voice_single) 적용 (메아리/하울링 완전 박멸)
   - 맑고 또렷한 표준 한국어 아나운서 음성 1회 깨끗하게 출력!
2. 두 눈 감김(졸음운전) 정확히 10초 감지 후 비상정차 발동:
   - 0.0s ~ 5.0s: 실시간 초단위 카운트 (1.0s, 2.0s...) & 삐-삐- 주의 경고
   - 5.0s 도달 즉시: "5초 후 비상정차를 시도합니다." 초고음질 한국어 음성 출력!
   - 5.0s ~ 10.0s: 대형 적색 5초 카운트다운 타이머 게이지 (5.0s -> 0.0s) 표출
   - 10.0s 도달 시: "비상 감속을 시작합니다. 우측 갓길로 안전하게 정차합니다." 음성 출력 후 갓길 자율 정차!
   - 10초 이전 눈을 뜨면 즉시 카운트다운 취소 및 정상 주행 복귀!
3. 눈썹 오검출을 완벽 박멸한 초정밀 눈 영역(세로 28%~50%) 동공 명암비 감지 알고리즘 탑재!
4. 머리 숙임 & 뒤로 기절 감지 시에도 동일하게 5초 음성 멘트 및 비상정차 연동!
5. 얼굴감지 노란색 범위를 화면 전체(가로 2%~98%, 세로 2%~98%)로 최대 확장!
6. 후방카메라(CH-5) 차량 역동적 움직임 (앞차만큼 실시간으로 움직이게):
   - 우리 차 속도 및 앞차 가감속에 맞춰 14m~30m 사이를 원근감 있게 실시간 왕복!
   - 리얼 승용차 디테일: 앞유리, 사이드미러, 그릴, LED 프로젝션 헤드라이트 광채, 번호판
   - 우리 버스 비상 감속 시 뒤차가 브레이크 밟고 좌측 2차선으로 회피 추월해 지나가는 모션 연출!
7. 전방카메라(CH-4) 앞차 급감속 연동 자동 제동 (AEB / 스마트 크루즈 컨트롤)
"""

import cv2
import numpy as np
import time
import math
import random
import os
import threading
import winsound
import pygame
from PIL import Image, ImageDraw, ImageFont

# 폰트 로드
font_path = "C:/Windows/Fonts/malgun.ttf"
font_bold_path = "C:/Windows/Fonts/malgunbd.ttf"
font_huge = ImageFont.truetype(font_bold_path, 26)
font_large = ImageFont.truetype(font_bold_path, 20)
font_mid = ImageFont.truetype(font_path, 13)
font_small = ImageFont.truetype(font_bold_path, 11)
font_micro = ImageFont.truetype(font_path, 10)
font_bold = ImageFont.truetype(font_bold_path, 13)
font_title = ImageFont.truetype(font_bold_path, 20)

script_dir = os.path.dirname(os.path.abspath(__file__))
SOUND_DIR = os.path.join(script_dir, "safetyon_sounds")
if not os.path.exists(SOUND_DIR):
    SOUND_DIR = r"C:\Users\LENOVO\Desktop\safetyon_sounds"

class DualSoundEngine:
    """pygame + winsound 최적화 사운드 엔진 (소리 100% 무조건 보장, 음성 하울링 0%)"""
    def __init__(self):
        try:
            pygame.mixer.init(frequency=44100, size=-16, channels=2, buffer=512)
            pygame.mixer.set_num_channels(8)
            self.pg_ok = True
        except Exception:
            self.pg_ok = False

        self.snd_tick_hi = self._load_snd("tick_hi.wav")
        self.snd_tick_lo = self._load_snd("tick_lo.wav")
        self.snd_beep_side = self._load_snd("beep_side.wav")
        self.snd_hazard_beep = self._load_snd("hazard_beep.wav")
        self.snd_siren = self._load_snd("siren_119.wav")
        self.snd_announce_5sec = self._load_snd("announce_5sec.wav")
        self.snd_announce_stop = self._load_snd("announce_stop.wav")
        self.snd_voice_sua = self._load_snd("voice_sua.wav")
        self.snd_voice_flood = self._load_snd("voice_flood.wav")
        self.snd_voice_battery = self._load_snd("voice_battery.wav")
        self.snd_voice_incapacitated = self._load_snd("voice_incapacitated.wav")
        self.snd_voice_safe_stop = self._load_snd("voice_safe_stop.wav")

        self.announced_sua = False
        self.announced_flood = False
        self.announced_battery = False
        self.announced_safe_stop = False
        self.announced_incapacitated = False
        self.is_muted = False

        self.last_blink_time = 0
        self.blink_step = False
        self.last_side_beep_time = 0
        self.last_hazard_beep_time = 0
        self.last_siren_time = 0

        self.announced_5sec = False
        self.announced_stop = False

    def _load_snd(self, filename):
        path = os.path.join(SOUND_DIR, filename)
        if self.pg_ok and os.path.exists(path):
            try:
                snd = pygame.mixer.Sound(path)
                snd.set_volume(1.0)
                return snd
            except Exception:
                pass
        return None

    def play_blink_tick(self):
        """깜빡이 릴레이 딱-톡 소리 출력"""
        now = time.time()
        if now - self.last_blink_time >= 0.44:
            self.last_blink_time = now
            self.blink_step = not self.blink_step
            snd = self.snd_tick_hi if self.blink_step else self.snd_tick_lo
            fn = "tick_hi.wav" if self.blink_step else "tick_lo.wav"
            self._dual_play(snd, fn)

    def play_side_alert(self):
        """옆에 차/오토바이 사각지대 접근 시 '삐-삐-' 소리 출력"""
        now = time.time()
        if now - self.last_side_beep_time >= 0.85:
            self.last_side_beep_time = now
            self._dual_play(self.snd_beep_side, "beep_side.wav")

    def play_hazard_beep(self):
        """비상 경고 부저음 출력"""
        now = time.time()
        if now - self.last_hazard_beep_time >= 0.45:
            self.last_hazard_beep_time = now
            self._dual_play(self.snd_hazard_beep, "hazard_beep.wav")

    def play_119_siren(self):
        """119 구급 사이렌 소리 출력 (삐뽀-삐뽀)"""
        now = time.time()
        if now - self.last_siren_time >= 2.3:
            self.last_siren_time = now
            self._dual_play(self.snd_siren, "siren_119.wav")

    def play_announce_5sec(self):
        """'5초 후 비상정차를 시도합니다' 한국어 음성 멘트 - 단일 채널 깨끗한 원음 출력"""
        if not self.announced_5sec:
            self.announced_5sec = True
            self._play_voice_single(self.snd_announce_5sec, "announce_5sec.wav")

    def play_announce_stop(self):
        """'비상 감속을 시작합니다' 한국어 음성 멘트 - 단일 채널 깨끗한 원음 출력"""
        if not self.announced_stop:
            self.announced_stop = True
            self._play_voice_single(self.snd_announce_stop, "announce_stop.wav")

    def play_voice_sua(self):
        """급발진 차단 음성 안내"""
        if not self.announced_sua:
            self.announced_sua = True
            self._play_voice_single(self.snd_voice_sua, "voice_sua.wav")

    def play_voice_flood(self):
        """침수 탈출 음성 안내"""
        if not self.announced_flood:
            self.announced_flood = True
            self._play_voice_single(self.snd_voice_flood, "voice_flood.wav")

    def play_voice_battery(self):
        """배터리 하부 충격 방호 음성 안내"""
        if not self.announced_battery:
            self.announced_battery = True
            self._play_voice_single(self.snd_voice_battery, "voice_battery.wav")

    def play_voice_incapacitated(self):
        """운전자 기절 감지 음성 안내"""
        if not self.announced_incapacitated:
            self.announced_incapacitated = True
            self._play_voice_single(self.snd_voice_incapacitated, "voice_incapacitated.wav")

    def play_voice_safe_stop(self):
        """갓길 정차 완료 음성 안내"""
        if not self.announced_safe_stop:
            self.announced_safe_stop = True
            self._play_voice_single(self.snd_voice_safe_stop, "voice_safe_stop.wav")

    def reset_announcements(self):
        """정상 복귀 시 멘트 플래그 리셋"""
        self.announced_5sec = False
        self.announced_stop = False
        self.announced_sua = False
        self.announced_flood = False
        self.announced_battery = False
        self.announced_safe_stop = False
        self.announced_incapacitated = False

    def _play_voice_single(self, pg_snd, filename):
        """음성 멘트는 에코/하울링 방지를 위해 오직 1개 채널로만 선명하게 단독 재생!"""
        if self.is_muted:
            return
        if pg_snd is not None:
            try:
                pg_snd.play()
                return
            except Exception:
                pass
        path = os.path.join(SOUND_DIR, filename)
        if os.path.exists(path):
            threading.Thread(target=lambda: winsound.PlaySound(path, winsound.SND_FILENAME), daemon=True).start()

    def toggle_mute(self):
        self.is_muted = not self.is_muted
        return self.is_muted

    def _dual_play(self, pg_snd, filename):
        """효과음(깜빡이, 경고음, 사이렌) 이중 출력"""
        if self.is_muted:
            return
        if pg_snd is not None:
            try:
                pg_snd.play()
            except Exception:
                pass
        path = os.path.join(SOUND_DIR, filename)
        if os.path.exists(path):
            threading.Thread(target=lambda: winsound.PlaySound(path, winsound.SND_FILENAME), daemon=True).start()

class TrafficVehicle:
    """고속도로 통행 차량 (절대 겹치지 않는 지능형 주행)"""
    def __init__(self, lane_col, initial_y, vtype, plate_str, speed_kmh):
        self.lane_col = lane_col
        self.vtype = vtype
        self.plate = plate_str
        self.speed = speed_kmh
        self.y = initial_y

        if self.vtype == 'BUS':
            self.w, self.h = 52, 105
            self.color = (35, 75, 135)
            self.border_color = (80, 160, 255)
        elif self.vtype == 'TRUCK':
            self.w, self.h = 48, 90
            self.color = (55, 60, 70)
            self.border_color = (180, 180, 190)
        elif self.vtype == 'MOTO':
            self.w, self.h = 24, 42
            self.color = (180, 35, 35)
            self.border_color = (255, 70, 70)
        elif self.vtype == 'SUV':
            self.w, self.h = 42, 70
            self.color = (40, 50, 60)
            self.border_color = (140, 200, 255)
        else: # SEDAN
            self.w, self.h = 38, 62
            self.color = (28, 38, 48)
            self.border_color = (100, 220, 255)

    def update(self, my_speed, dt):
        rel_speed_kmh = self.speed - my_speed
        if my_speed <= 5.0:
            vy = -self.speed * 7.5
        else:
            vy = -rel_speed_kmh * 7.5

        self.y += vy * dt

        if self.y < -180:
            self.y = random.uniform(620, 760)
        elif self.y > 880:
            self.y = random.uniform(-150, -80)

def update_lane_traffic(car_list, my_speed, dt):
    """차량 간 안전거리 유지 및 겹침 방지 (ACC 알고리즘)"""
    for car in car_list:
        car.update(my_speed, dt)

    car_list.sort(key=lambda c: c.y)
    for i in range(1, len(car_list)):
        front = car_list[i-1]
        rear = car_list[i]
        if front.lane_col == rear.lane_col:
            min_gap = front.h + 85
            if rear.y - front.y < min_gap:
                rear.y = front.y + min_gap
                rear.speed = min(rear.speed, front.speed)

def log_emergency_dispatch(gps_lat, gps_lon, location_desc, reason_desc):
    """3자 비상구난 e-Call 공식 로그 생성"""
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    log_text = f"""========================================================================
[세이프티온 e-Call] 3자 동시 비상구난 전화 및 위치 SMS 전송 공식 보고서
발송일시: {now_str}
차량정보: 주식회사 세이프티온 시험차량 (경기70아 1234)
발생사건: 운전자 {reason_desc} 감지 -> "5초 후 비상정차" 음성 안내 후 갓길 안전정차 완료
정차위치: {location_desc} (GPS: {gps_lat:.4f}, {gps_lon:.4f})
------------------------------------------------------------------------
[1] 119 소방청 긴급상황실 (핫라인 전화 + e-Call 패킷)
    - 수신처: 119 종합상황실 구급상황관리센터
    - 연결상태: 자동 음성전화 연결 완료 & GPS 좌표 100% 전송
    - 전송전문: "경부선 382.4km 하행, 버스 운전자 {reason_desc}, 
                승객 34명 안전 5차선 갓길 정차 완료, 즉시 구급차 출동 요망"

[2] 운송회사 관제센터 (서울고속 중앙관제팀)
    - 수신처: 02-1588-0000 (운송사 종합상황실)
    - 연결상태: LTE-M 비상관제망 실시간 채널 연결 완료
    - 전송전문: "경기70아 1234호 차량 운전자 {reason_desc} 비상정차.
                승객 안전 확보(도어 자동 언락), 대체 버스 긴급 배차 요망"

[3] 보호자/가족 긴급 안심 SMS 문자 발송
    - 수신처: 010-5121-1353 (변귀섭 대표이사 지정 비상연락처)
    - 발송상태: [SMS 발송 성공]
    - 문자내용: "[세이프티온 안심알림] 변귀섭 기사님 운전 중 {reason_desc} 감지되어 
                차량이 5차선 갓길에 안전하게 자율 다단감속 정차되었습니다. 
                119 구급대가 출동 중입니다. (위치: {location_desc})"
========================================================================
"""
    log_path = r"C:\Users\LENOVO\Desktop\세이프티온_비상긴급호출_전송로그.txt"
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log_text)
    except Exception:
        pass


def log_flood_dispatch(gps_lat, gps_lon, location_desc):
    """침수 고립 시 도어 글래스 자동 파쇄 및 119 수난구조 공식 로그 생성"""
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    log_text = f"""========================================================================
[세이프티온 침수탈출] 수위 감지 기반 도어 글래스 자동 파쇄 비상구난 보고서
발송일시: {now_str}
차량정보: 주식회사 세이프티온 시험차량 (경기70아 1234)
발생사건: 지하차도 침수 및 급격한 하천 범람 감지 -> 침수위 25cm 도달
대응조치: 
  1. 외부 수압 145kgf 감지로 도어 개폐 불가 상태 즉각 크로스체크 완료
  2. 세이프티온 '도어 글래스 자동 파쇄 펀칭 모듈' 0.05초 초고속 동시 격발!
  3. 운전석 및 탑승자 윈도우 파쇄로 골든타임 탈출로 100% 확보
  4. 119 수난구조대 및 해경에 GPS 실시간 조난 e-Call 패킷 자동 전송 완료
정차위치: {location_desc} (GPS: {gps_lat:.4f}, {gps_lon:.4f})
========================================================================
"""
    log_path = r"C:\Users\LENOVO\Desktop\세이프티온_침수탈출_긴급구조_로그.txt"
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log_text)
    except Exception:
        pass


def log_sua_dispatch(gps_lat, gps_lon, location_desc):
    """급발진/페달 오조작 비상 제동 공식 로그 생성"""
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    log_text = f"""========================================================================
[세이프티온 급발진 차단] 엔진 동력 물리 컷오프 & 150kgf 비상 제동 보고서
발송일시: {now_str}
차량정보: 주식회사 세이프티온 시험차량 (경기70아 1234)
발생사건: 가속페달 98% 오조작 및 급발진 비정상 가속(125km/h 돌파) 감지
대응조치: 
  1. 엔진/구동모터 물리 전원 릴레이 즉각 컷오프 (0.1초 이내 구동력 완전 소멸)
  2. 특허 10-2026-0206816 '2층 시소반전 가압 푸시로드' 모듈 가동
     -> 브레이크 페달에 150kgf 기계식 물리 제동력 직결 강제 가압!
  3. ECU 전자제어 먹통 및 브레이크 진공 상실 상황에서도 100% 물리 제동 실현
  4. 0.38G 비상 다단 감속으로 안전 정차(0.0km/h) 완료 및 2차 추돌 원천 방지
정차위치: {location_desc} (GPS: {gps_lat:.4f}, {gps_lon:.4f})
========================================================================
"""
    log_path = r"C:\Users\LENOVO\Desktop\세이프티온_급발진차단_제동로그.txt"
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log_text)
    except Exception:
        pass


def log_battery_dispatch(gps_lat, gps_lon, location_desc):
    """전기차 배터리팩 하부 관통 충돌 및 화재 방호 공식 로그 생성"""
    now_str = time.strftime("%Y-%m-%d %H:%M:%S")
    log_text = f"""========================================================================
[세이프티온 EV배터리 방호] 하부 충돌 감지 기반 전단농화 & 자가밀폐 방호 보고서
발송일시: {now_str}
차량정보: 주식회사 세이프티온 시험차량 (경기70아 1234)
발생사건: 고속 주행 중 도로 낙하물/금속 파편 배터리팩 하부 180J 강타 감지
대응조치: 
  1. 특허 10-2026-0227055 전단농화(STF) 복합 하부 쉴드 순간 경화로 관통 저지
  2. 자가밀폐 젤(Self-healing Gel) 미세 크랙 0.05초 즉각 침투 밀봉 (방수/방기)
  3. 셀 격벽 열팽창 흑연 방화 장벽 가동으로 인접 셀 열전파 및 열폭주 원천 격리
  4. 고전압 파워 릴레이 즉시 차단 및 차량 안전 정차 유도 완료
정차위치: {location_desc} (GPS: {gps_lat:.4f}, {gps_lon:.4f})
========================================================================
"""
    log_path = r"C:\Users\LENOVO\Desktop\세이프티온_전기차배터리방호_로그.txt"
    try:
        with open(log_path, "w", encoding="utf-8") as f:
            f.write(log_text)
    except Exception:
        pass

def main():
    face_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_frontalface_default.xml')
    eye_cascade = cv2.CascadeClassifier(cv2.data.haarcascades + 'haarcascade_eye.xml')

    cap = cv2.VideoCapture(0)
    win_name = "SafetyON Electronic Digital Rearview Mirror (CMS & DSM Simulator)"
    cv2.namedWindow(win_name, cv2.WINDOW_NORMAL)
    cv2.resizeWindow(win_name, 1360, 680)

    sound_engine = DualSoundEngine()

    mouse_cmd_queue = []
    def on_mouse(event, x, y, flags, param):
        if event == cv2.EVENT_LBUTTONDOWN:
            if 640 <= y <= 678:
                if 32 <= x <= 175:
                    mouse_cmd_queue.append(' ')
                elif 182 <= x <= 335:
                    mouse_cmd_queue.append('a')
                elif 342 <= x <= 485:
                    mouse_cmd_queue.append('f')
                elif 492 <= x <= 640:
                    mouse_cmd_queue.append('b')
                elif 647 <= x <= 765:
                    mouse_cmd_queue.append('l')
                elif 772 <= x <= 885:
                    mouse_cmd_queue.append('	')
                elif 892 <= x <= 985:
                    mouse_cmd_queue.append('r')
                elif 992 <= x <= 1075:
                    mouse_cmd_queue.append('q')

    cv2.setMouseCallback(win_name, on_mouse)

    # 1. 좌측 1-2차로 통행 차량 (CH-2)
    left_traffic = [
        TrafficVehicle(0, initial_y=80, vtype='BUS', plate_str="경기70아 7281", speed_kmh=104.0),
        TrafficVehicle(1, initial_y=240, vtype='TRUCK', plate_str="서울82바 3912", speed_kmh=88.0),
        TrafficVehicle(1, initial_y=490, vtype='SEDAN', plate_str="34노 8912", speed_kmh=112.0)
    ]

    # 2. 우측 4-5차로 통행 차량 (CH-3)
    right_traffic = [
        TrafficVehicle(0, initial_y=200, vtype='MOTO', plate_str="경기 수원 가 5423", speed_kmh=102.0),
        TrafficVehicle(1, initial_y=430, vtype='SUV', plate_str="152하 9034", speed_kmh=110.0)
    ]

    # 눈 감김 지속 시간 타이머
    eyes_closed_timer_start = None
    eyes_open_confidence = 1.0 # 0.0(감김) ~ 1.0(뜸)
    pupil_open_ratio = 95
    left_eye_open = True
    right_eye_open = True
    missing_driver_start = None

    state = "NORMAL" # NORMAL, COUNTDOWN_5SEC, EVADE_LEFT_PASS, EVADE_LANE_CHANGE, EVADE_BRAKING, STOPPED
    current_lane_f = 3.0
    speed = 82.0
    g_force = 0.0
    evade_start_time = 0
    countdown_start_time = 0
    countdown_reason = ""
    heart_rate = 74
    road_offset = 0

    steer_angle = 0.0
    guardrail_dist = 12.8
    hazard_lamp_state = False
    left_turn_signal_state = False
    logged_dispatch = False
    flood_start_time = 0
    flood_water_level = 0.0

    sua_start_time = 0
    logged_sua = False
    presentation_timer_start = None

    battery_start_time = 0
    logged_battery = False
    battery_temp = 32.0

    is_fullscreen = False

    left_evade_start_time = 0
    right_merge_status = ""

    # 전방 카메라 원근감 이동 차량 파라미터
    front_lead_dist = 32.0   # 우리 차선 선행차 (32m)
    front_lead_speed = 82.0
    front_left_dist = 45.0   # 좌측 2차선 추월차
    front_right_dist = 28.0  # 우측 4차선 트럭
    front_brake_active = False

    # 후방 카메라 원근감 이동 차량 파라미터 (앞차만큼 역동적 움직임)
    rear_lead_dist = 22.0    # 직후방 추종차 거리 (14m ~ 30m)
    rear_lead_speed = 82.0
    rear_lead_offset_x = 0.0 # 우리 버스 감속 시 좌측 회피 기동
    rear_left_dist = 15.0    # 좌측 후방 추월차
    rear_tail_blink = False

    gps_lat, gps_lon = 37.3421, 126.9812
    location_desc = "경부고속도로 하행 382.4km (5차선 최우측 갓길 정차)"

    last_time = time.time()
    sim_time = 0

    while True:
        now = time.time()
        dt = max(0.001, min(0.08, now - last_time))
        last_time = now
        sim_time += dt

        ret, cam_frame = cap.read()
        if not ret:
            cam_frame = np.zeros((480, 640, 3), dtype=np.uint8)

        cam_frame = cv2.flip(cam_frame, 1)
        cam_h, cam_w = cam_frame.shape[:2]
        gray = cv2.cvtColor(cam_frame, cv2.COLOR_BGR2GRAY)

        # -------------------------------------------------------------------------
        # 🌟 [대표님 핵심 요청 1]: 얼굴감지 노란색 범위를 화면 전체(가로 2%~98%, 세로 2%~98%)로 최대 확장!
        # -------------------------------------------------------------------------
        roi_x1, roi_x2 = int(cam_w * 0.02), int(cam_w * 0.98)
        roi_y1, roi_y2 = int(cam_h * 0.02), int(cam_h * 0.96)

        # 피부색 영역 및 상/하단 분할 분석
        ycrcb = cv2.cvtColor(cam_frame, cv2.COLOR_BGR2YCrCb)
        skin_mask = cv2.inRange(ycrcb, np.array([0, 133, 77]), np.array([255, 175, 128]))

        half_h = int(cam_h * 0.48)
        skin_top = cv2.countNonZero(skin_mask[:half_h, :])
        skin_bottom = cv2.countNonZero(skin_mask[half_h:, :])
        skin_total = skin_top + skin_bottom

        # 상단/중단 어두운 머리카락 픽셀
        dark_hair_top = np.sum(gray[:int(cam_h * 0.65), :] < 65)

        faces = face_cascade.detectMultiScale(gray, 1.2, 5, minSize=(80, 80))
        face_detected = len(faces) > 0
        driver_slumped = False
        hand_occlusion = False
        head_dropped = False     # 머리 앞으로 푹 숙임 (전방 전도 - 사진 2번)
        head_tilted_back = False # 머리 뒤로 너무 감/기절 (후방 전도 - 사진 3번)
        is_eyes_closed_frame = False # 현재 프레임에서 눈이 감겼는지 여부

        if face_detected:
            (fx, fy, fw, fh) = faces[0]
            # 얼굴 위치에 따른 머리 숙임/젖힘 판정
            if fy > int(cam_h * 0.40) or (fy + fh > int(cam_h * 0.88)):
                head_dropped = True
                cv2.rectangle(cam_frame, (fx, fy), (fx + fw, fy + fh), (0, 0, 255), 3)
            elif fy < int(cam_h * 0.06):
                head_tilted_back = True
                cv2.rectangle(cam_frame, (fx, fy), (fx + fw, fy + fh), (0, 0, 255), 3)
            else:
                cv2.rectangle(cam_frame, (fx, fy), (fx + fw, fy + fh), (0, 0, 255), 2)

            # ---------------------------------------------------------------------
            # 🌟 [눈썹 오검출 완전 배제 및 초정밀 눈 감김 감별 알고리즘]
            # 눈썹(15%~26%)을 완전히 배제하고 오직 눈/동공 영역(28%~50%)만 타겟팅!
            # ---------------------------------------------------------------------
            eye_y1 = fy + int(fh * 0.28)
            eye_y2 = fy + int(fh * 0.50)
            eye_zone = gray[eye_y1:eye_y2, fx:fx + fw]

            # 눈썹이 배제된 순수 안구 영역에서 Haar 눈 검출
            eyes = eye_cascade.detectMultiScale(eye_zone, scaleFactor=1.10, minNeighbors=3, minSize=(14, 14))
            detected_eyes_count = len(eyes)

            # 안구 영역의 어두운 동공 픽셀 분석 (눈을 감으면 동공이 사라져 밝기 상승)
            mid_w = int(fw * 0.5)
            left_eye_roi = eye_zone[:, :mid_w]
            right_eye_roi = eye_zone[:, mid_w:]

            # 10% 최저 밝기 (동공 밝기)
            pupil_l = np.percentile(left_eye_roi, 8) if left_eye_roi.size > 0 else 100
            pupil_r = np.percentile(right_eye_roi, 8) if right_eye_roi.size > 0 else 100

            # Haar 검출 위치 분석 (좌안 vs 우안)
            haar_has_left = any((ex + ew / 2) < mid_w for (ex, ey, ew, eh) in eyes)
            haar_has_right = any((ex + ew / 2) >= mid_w for (ex, ey, ew, eh) in eyes)

            # 좌안 / 우안 개별 개도 판정 (어두운 동공 픽셀 및 Haar 검출 융합)
            if haar_has_left != haar_has_right:
                left_eye_open = haar_has_left
                right_eye_open = haar_has_right
            elif abs(pupil_l - pupil_r) >= 12:
                # 한쪽 동공이 다른 쪽보다 확연히 어두움 -> 어두운 쪽이 열린 눈!
                left_eye_open = (pupil_l < pupil_r)
                right_eye_open = (pupil_r < pupil_l)
            elif (pupil_l < 62 or pupil_r < 62) or detected_eyes_count >= 1:
                left_eye_open = True
                right_eye_open = True
            else:
                left_eye_open = False
                right_eye_open = False

            # 동공 개도율 계산 (대표님 요청: 한쪽 눈 감으면 50%!)
            if left_eye_open and right_eye_open:
                pupil_open_ratio = 95
                eyes_open_confidence = min(1.0, eyes_open_confidence + dt * 4.0)
            elif left_eye_open or right_eye_open:
                # 🌟 [대표님 요청 핵심] 한쪽 눈 감김 -> 50%
                pupil_open_ratio = 50
                eyes_open_confidence = 0.55 # 10초 비상정차 안 걸리고 주의 모드 유지
            else:
                # 두 눈 모두 감김 -> 0%
                pupil_open_ratio = 0
                eyes_open_confidence = max(0.0, eyes_open_confidence - dt * 5.0)

            # 두 눈 모두 감겨 신뢰도 0.35 미만이면 10초 비상정차 타이머 확정!
            is_eyes_closed_frame = (eyes_open_confidence < 0.35)

            # 시각화 박스 (열린 눈에만 박스 표시)
            for (ex, ey, ew, eh) in eyes[:2]:
                cv2.rectangle(cam_frame, (fx + ex, eye_y1 + ey), (fx + ex + ew, eye_y1 + ey + eh), (255, 220, 0), 2)

            # 한쪽 눈만 감겼을 때 감긴 쪽에 주황색 수평선 표시
            if left_eye_open and not right_eye_open:
                cv2.line(cam_frame, (fx + mid_w + int(mid_w * 0.15), eye_y1 + int((eye_y2 - eye_y1) * 0.5)),
                                    (fx + fw - int(mid_w * 0.15), eye_y1 + int((eye_y2 - eye_y1) * 0.5)), (0, 140, 255), 3)
            elif right_eye_open and not left_eye_open:
                cv2.line(cam_frame, (fx + int(mid_w * 0.15), eye_y1 + int((eye_y2 - eye_y1) * 0.5)),
                                    (fx + mid_w - int(mid_w * 0.15), eye_y1 + int((eye_y2 - eye_y1) * 0.5)), (0, 140, 255), 3)
            elif is_eyes_closed_frame:
                cv2.line(cam_frame, (fx + int(fw * 0.15), eye_y1 + int((eye_y2 - eye_y1) * 0.5)),
                                    (fx + int(fw * 0.85), eye_y1 + int((eye_y2 - eye_y1) * 0.5)), (0, 0, 255), 3)
        else:
            # 얼굴 미검출 시: 머리 숙임 vs 뒤로 기절 vs 손가림 감별
            if dark_hair_top > 6800 and skin_top < 5000:
                head_dropped = True
            elif (skin_bottom >= 1500) and (skin_top < 2200) and (dark_hair_top < 3800):
                head_tilted_back = True
            elif skin_total >= 2800:
                hand_occlusion = True

        # 전체 노란색 감지 프레임 그리기 (대표님 요청: 최대한 넓게 화면 전체 커버)
        box_color = (0, 0, 255) if (head_dropped or head_tilted_back or is_eyes_closed_frame) else ((0, 220, 255) if hand_occlusion else (0, 255, 255))
        cv2.rectangle(cam_frame, (roi_x1, roi_y1), (roi_x2, roi_y2), box_color, 2)

        # -------------------------------------------------------------------------
        # 🌟 [대표님 핵심 요청 2]: 두 눈 10초간 감고 있으면 비상정차 작동!
        # - 0s ~ 5s: 실시간 초단위 카운트 누적
        # - 5s 도달: "5초 후 비상정차를 시도합니다." 음성 멘트 출력 & 5초 대형 카운트다운 게이지 표출!
        # - 10s 도달: "비상 감속을 시작합니다." 음성과 함께 최우측 갓길 비상정차 돌입!
        # -------------------------------------------------------------------------
        if is_eyes_closed_frame and not (head_dropped or head_tilted_back):
            if eyes_closed_timer_start is None:
                eyes_closed_timer_start = now
            eyes_closed_dur = now - eyes_closed_timer_start

            # 2초 이상 눈 감을 시 간헐적 삐-삐- 경고음
            if eyes_closed_dur >= 2.0 and state == "NORMAL":
                sound_engine.play_side_alert()

            # 5.0초 도달 시: 5초 카운트다운 모드 진입 및 멘트 출력!
            if eyes_closed_dur >= 5.0 and state == "NORMAL":
                state = "COUNTDOWN_5SEC"
                countdown_start_time = now
                countdown_reason = "두 눈 감김(졸음운전)"
                sound_engine.play_announce_5sec()

            # 총 10.0초 도달 시: 비상 감속 및 갓길 정차 발동!
            if eyes_closed_dur >= 10.0 and state in ["NORMAL", "COUNTDOWN_5SEC"]:
                sound_engine.play_announce_stop()
                state = "EVADE_LANE_CHANGE"
                evade_start_time = now
                left_turn_signal_state = False

            # 심박수 연동 (졸음 시 서맥 50bpm)
            heart_rate = max(45, int(74 - eyes_closed_dur * 2.8))
        else:
            # 🌟 눈을 번쩍 뜨면 10초 타이머 즉각 리셋!
            eyes_closed_timer_start = None
            eyes_closed_dur = 0.0
            if state == "COUNTDOWN_5SEC" and countdown_reason == "두 눈 감김(졸음운전)":
                state = "NORMAL"
                countdown_start_time = 0
                heart_rate = 74
                sound_engine.reset_announcements()

        # -------------------------------------------------------------------------
        # 머리 숙임(전방 전도) / 뒤로 기절(후방 전도) 처리 (동일 5초 멘트 카운트다운)
        # -------------------------------------------------------------------------
        head_abnormal = (head_dropped or head_tilted_back)
        if head_abnormal and state in ["NORMAL", "COUNTDOWN_5SEC"] and not is_eyes_closed_frame:
            if state == "NORMAL":
                state = "COUNTDOWN_5SEC"
                countdown_start_time = now
                countdown_reason = "머리 숙임(전방 전도)" if head_dropped else "뒤로 기절(후방 전도)"

            head_dur = now - countdown_start_time
            if head_dur >= 0.2:
                sound_engine.play_announce_5sec()

            heart_rate = max(42, int(74 - head_dur * 6.0))

            if head_dur >= 5.0:
                sound_engine.play_announce_stop()
                state = "EVADE_LANE_CHANGE"
                evade_start_time = now
                left_turn_signal_state = False
        elif not head_abnormal and state == "COUNTDOWN_5SEC" and countdown_reason != "두 눈 감김(졸음운전)":
            state = "NORMAL"
            countdown_start_time = 0
            heart_rate = 74
            sound_engine.reset_announcements()

        # 운전자 완전 이탈 8초 처리
        if not face_detected and not (head_dropped or head_tilted_back or hand_occlusion):
            if missing_driver_start is None:
                missing_driver_start = now
            if (now - missing_driver_start) >= 8.0 and state == "NORMAL":
                sound_engine.play_announce_stop()
                state = "EVADE_LANE_CHANGE"
                evade_start_time = now
        else:
            missing_driver_start = None

        # -------------------------------------------------------------------------
        # 🌟 [대표님 핵심 요청 3]: 전방 카메라 및 후방 카메라 실시간 연동 움직임!
        # -------------------------------------------------------------------------
        # 1. 전방 카메라 (앞차 감속 감응 AEB / 스마트 크루즈)
        cycle_t = sim_time % 14.0
        if 5.0 <= cycle_t <= 9.5 and state == "NORMAL":
            front_brake_active = True
            front_lead_speed = max(42.0, front_lead_speed - dt * 25.0)
            front_lead_dist = max(13.5, front_lead_dist - dt * 5.5)
            speed = max(front_lead_speed, speed - dt * 22.0)
            g_force = -0.18
        else:
            front_brake_active = False
            front_lead_speed = min(82.0, front_lead_speed + dt * 15.0)
            front_lead_dist = min(32.0, front_lead_dist + dt * 4.5)
            if state == "NORMAL":
                speed = min(82.0, speed + dt * 12.0)
                g_force = 0.0

        # 전방 좌측 2차선 추월차 & 우측 4차선 트럭
        front_left_dist = 20.0 + (sim_time * 6.5) % 50.0
        front_right_dist = 18.0 + (sim_time * 3.5) % 40.0

        # 2. 🌟 후방 카메라 (3차선 정차 시 뒷차도 함께 정차하는 지능형 후방 추돌 방지 로직)
        if (current_lane_f <= 3.8) and (speed <= 0.0 or state in ["SUA_EMERGENCY", "BATTERY_EMERGENCY"] or front_brake_active):
            # 🌟 [대표님 요청 핵심] 3차선에서 우리 차가 감속/정차하면 뒷차도 3차선 중앙에서 멈춤!
            rear_lead_offset_x = 0.0
            rear_tail_blink = True
            if speed <= 0.0:
                # 우리 차 완전 정차 시 뒷차도 안전거리 8.5m에 부드럽게 완전 정차!
                rear_lead_dist = max(8.5, rear_lead_dist - dt * 16.0)
            else:
                # 감속 중일 때 안전거리 12.0m 유지하며 감속
                rear_lead_dist = max(12.0, rear_lead_dist - dt * 9.0)

        elif state in ["EVADE_LANE_CHANGE", "EVADE_BRAKING", "STOPPED"] and current_lane_f > 3.8:
            # 우측 갓길로 이동한 경우: 3차선에 있던 뒷차는 좌측 2차선으로 회피 추월
            rear_lead_offset_x = min(140.0, rear_lead_offset_x + dt * 48.0)
            rear_lead_dist = min(55.0, rear_lead_dist + dt * 9.0)
            rear_tail_blink = (int(now * 3.0) % 2 == 0)

        else:
            # 일반 주행 상태
            rear_lead_offset_x = 0.0
            rear_lead_dist = 22.0 + math.sin(sim_time * 1.8) * 5.5
            rear_tail_blink = False

        rear_left_dist = 10.0 + (sim_time * 8.0) % 45.0

        # -------------------------------------------------------------------------
        # 사각지대 차량 접근 시 '삐-삐-' 경고음
        # -------------------------------------------------------------------------
        side_vehicle_danger = False
        for v in left_traffic:
            if 150 < v.y < 450 and state in ["NORMAL", "COUNTDOWN_5SEC"]:
                side_vehicle_danger = True
                break
        if not side_vehicle_danger:
            for v in right_traffic:
                if 150 < v.y < 450 and state in ["NORMAL", "COUNTDOWN_5SEC"]:
                    side_vehicle_danger = True
                    break

        if side_vehicle_danger:
            sound_engine.play_side_alert()

        # -------------------------------------------------------------------------
        # 왼쪽 깜빡이 켜고 차들을 안전하게 피하는 회피 주행 ([L] 키)
        # -------------------------------------------------------------------------
        if state == "EVADE_LEFT_PASS":
            left_elapsed = now - left_evade_start_time
            left_turn_signal_state = (int(now * 2.2) % 2 == 0)
            if left_turn_signal_state:
                sound_engine.play_blink_tick()

            if left_elapsed < 2.0:
                steer_angle = max(-12.0, steer_angle - dt * 15.0)
                current_lane_f = 3.0 - (left_elapsed / 2.0) * 1.0
                guardrail_dist = 12.8 + (left_elapsed / 2.0) * 3.5
            elif left_elapsed < 4.0:
                steer_angle = min(0.0, steer_angle + dt * 10.0)
                current_lane_f = 2.0
            else:
                state = "NORMAL"
                current_lane_f = 2.0
                steer_angle = 0.0
                left_turn_signal_state = False

        # -------------------------------------------------------------------------
        # 🌟 우측 차들을 먼저 안전하게 보내고 오른쪽으로 차선 변경 & 갓길 정차
        # -------------------------------------------------------------------------
        if state in ["EVADE_LANE_CHANGE", "EVADE_BRAKING", "STOPPED"]:
            hazard_lamp_state = (int(now * 2.2) % 2 == 0)
            if hazard_lamp_state:
                sound_engine.play_blink_tick()

            # 우측 차선 차량들의 지능형 양보 & 가속 회피 (실제 도로 상호작용)
            for v in right_traffic:
                if v.vtype == 'MOTO':
                    # 전방 오토바이는 안전거리 확보를 위해 신속히 가속 통과
                    v.speed = min(120.0, v.speed + dt * 25.0)
                else:
                    # 후방 SUV는 비상등을 보고 40m 뒤에서 부드럽게 감속 양보
                    if v.y > 280:
                        v.speed = max(45.0, v.speed - dt * 20.0)

        if state == "EVADE_LANE_CHANGE":
            evade_elapsed = now - evade_start_time
            sound_engine.play_voice_incapacitated()
            sound_engine.play_hazard_beep()

            # 🌟 실차 주행급 실키 스무스(S-Curve) 차선 이동 & 카운터스티어 조향 로직
            if evade_elapsed < 1.8:
                # 1단계: 안전 차간거리 모니터링 및 부드러운 감속 준비
                speed = max(75.0, 82.0 - evade_elapsed * 3.8)
                steer_angle = 0.0
                current_lane_f = 3.0
                guardrail_dist = 12.8
                g_force = -0.06
                right_merge_status = "[우측 감시] 인접 차로(SUV, 오토바이) 안전거리 45m 확인 중..."

            elif evade_elapsed < 4.4:
                # 2단계: 4차선으로 부드러운 S자 차선 진입 (코사인 가속 및 카운터스티어)
                p2 = (evade_elapsed - 1.8) / 2.6
                s2 = 0.5 - 0.5 * math.cos(math.pi * p2) # S-곡선 보간
                current_lane_f = 3.0 + s2 * 1.2 # 3.0 -> 4.2 차선
                guardrail_dist = 12.8 - s2 * 5.0 # 12.8m -> 7.8m
                # 실제 차선변경 핸들 회전: 진입 시 우측 9도, 차선 넘을 때 복귀, 반대방향 살짝 지지 후 0도 정렬
                steer_angle = 9.2 * math.sin(math.pi * p2 * 2.0)
                speed = max(66.0, 75.0 - p2 * 9.0)
                g_force = -0.10
                right_merge_status = f"[차선 변경 1단계] 4차로 안전 진입 중 (조향각 {steer_angle:.1f}° 자율 보정)"

            elif evade_elapsed < 7.2:
                # 3단계: 5차선 최우측 갓길 1.2m 부드러운 밀착 (코사인 가속 및 수평 정렬)
                p3 = (evade_elapsed - 4.4) / 2.8
                s3 = 0.5 - 0.5 * math.cos(math.pi * p3) # S-곡선 보간
                current_lane_f = 4.2 + s3 * 1.6 # 4.2 -> 5.8 갓길 안착
                guardrail_dist = 7.8 - s3 * 6.6 # 7.8m -> 1.2m 가드레일 밀착
                steer_angle = 5.8 * math.sin(math.pi * p3 * 2.0)
                speed = max(55.0, 66.0 - p3 * 11.0)
                g_force = -0.14
                right_merge_status = f"[갓길 안착 2단계] 가드레일 {guardrail_dist:.1f}m 밀착 및 핸들 0° 복귀"

            else:
                state = "EVADE_BRAKING"
                current_lane_f = 5.8
                guardrail_dist = 1.2
                steer_angle = 0.0
                g_force = -0.25
                right_merge_status = "[갓길 안착 완료] 0.25G 안전 다단 감속 브레이킹 시작"

        elif state == "EVADE_BRAKING":
            brake_elapsed = now - (evade_start_time + 7.2)
            steer_angle = 0.0
            guardrail_dist = 1.2
            current_lane_f = 5.8

            g_force = -0.25
            # 다단 감속 감속 곡선 (급격하지 않고 고급 승차감 유지)
            speed = max(0.0, 55.0 - (brake_elapsed ** 1.1) * 16.5)
            sound_engine.play_hazard_beep()
            right_merge_status = f"[갓길 다단 감속 중] 현재 속도 {speed:.1f}km/h (EPRV 전자비례 감속)"

            if speed <= 0.0:
                state = "STOPPED"
                speed = 0.0
                g_force = 0.0
                right_merge_status = "[최우측 갓길 정차 완료] 도어 잠금 해제 & 119 출동"
                if not logged_dispatch:
                    log_emergency_dispatch(gps_lat, gps_lon, location_desc, countdown_reason if countdown_reason else "10초 눈 감김")
                    logged_dispatch = True

        elif state == "STOPPED":
            speed = 0.0
            g_force = 0.0
            current_lane_f = 5.8
            steer_angle = 0.0
            guardrail_dist = 1.2
            right_merge_status = "[최우측 갓길 정차 100% 완료] 승객 안전 확보"
            sound_engine.play_119_siren()
            sound_engine.play_voice_safe_stop()

            if not logged_dispatch:
                log_emergency_dispatch(gps_lat, gps_lon, location_desc, countdown_reason if countdown_reason else "10초 눈 감김")
                logged_dispatch = True

        # -------------------------------------------------------------------------
        # 🚨 [A] 급발진(SUA / 페달 오조작) 비상 제동 모드 (특허 10-2026-0206816)
        # -------------------------------------------------------------------------
        elif state == "SUA_EMERGENCY":
            sua_elapsed = now - sua_start_time
            hazard_lamp_state = (int(now * 3.0) % 2 == 0)
            if hazard_lamp_state:
                sound_engine.play_blink_tick()
            sound_engine.play_hazard_beep()
            sound_engine.play_voice_sua()

            if sua_elapsed < 0.6:
                speed = min(125.0, 82.0 + sua_elapsed * 80.0)
                g_force = 0.45
                right_merge_status = "[급발진 감지] 가속페달 98% 이상치 감지 -> 125km/h 비정상 가속!"
            elif sua_elapsed < 1.3:
                speed = max(90.0, 125.0 - (sua_elapsed - 0.6) * 50.0)
                g_force = -0.32
                right_merge_status = "[특허 1단계] 엔진·모터 물리 전원 컷오프 -> 구동력 0.0kW 차단"
            elif sua_elapsed < 3.8:
                speed = max(0.0, 90.0 - (sua_elapsed - 1.3) * 36.0)
                g_force = -0.38
                right_merge_status = "[특허 2단계] 2층 시소반전 150kgf 브레이크 페달 직결 가압 중"
            else:
                speed = 0.0
                g_force = 0.0
                right_merge_status = "[완전 정차 성공] 150kgf 물리 제동 완료 -> 2차 추돌 0건 방지"
                if not logged_sua:
                    log_sua_dispatch(gps_lat, gps_lon, "도심 교차로 / 고속도로 실증구간")
                    logged_sua = True

        # -------------------------------------------------------------------------
        # 🔋 [B] 전기차(EV) 배터리팩 하부 충돌 및 화재 방호 모드 (특허 10-2026-0227055)
        # -------------------------------------------------------------------------
        elif state == "BATTERY_EMERGENCY":
            battery_elapsed = now - battery_start_time
            hazard_lamp_state = (int(now * 2.2) % 2 == 0)
            if hazard_lamp_state:
                sound_engine.play_blink_tick()
            sound_engine.play_hazard_beep()
            sound_engine.play_voice_battery()

            speed = max(0.0, 82.0 - battery_elapsed * 16.0)
            g_force = -0.20
            battery_temp = min(68.0, 32.0 + battery_elapsed * 6.0)

            if speed > 0.0:
                right_merge_status = f"[하부 충격 방호] STF 쉴드 경화 및 자가밀폐 젤 작동 중 ({speed:.1f}km/h)"
            else:
                speed = 0.0
                g_force = 0.0
                right_merge_status = "[안전 정차 완료] 열팽창 흑연 방화벽 격리 -> 열폭주 0% 차단 성공"
                if not logged_battery:
                    log_battery_dispatch(gps_lat, gps_lon, "고속화도로 실증구간")
                    logged_battery = True

        elif state == "FLOOD_EMERGENCY":
            flood_elapsed = now - flood_start_time
            flood_water_level = min(75.0, 15.0 + flood_elapsed * 5.5)
            sound_engine.play_voice_flood()
            sound_engine.play_hazard_beep()
            sound_engine.play_119_siren()
            speed = 0.0
            g_force = 0.0
            right_merge_status = f"[차량 침수 비상 탈출] 수위 {flood_water_level:.1f}cm -> 유리 파쇄 완료"

        elif state == "NORMAL" and not front_brake_active:
            hazard_lamp_state = False
            left_turn_signal_state = False
            logged_dispatch = False
            right_merge_status = ""

        shift_ratio = min(1.0, max(0.0, (current_lane_f - 2.0) / 3.8))
        road_offset = (road_offset + speed * dt * 8.0) % 100

        update_lane_traffic(left_traffic, speed, dt)
        update_lane_traffic(right_traffic, speed, dt)

        # -------------------------------------------------------------------------
        # 룸미러 일체형 캔버스 렌더링 (1360 x 680)
        # -------------------------------------------------------------------------
        canvas_w, canvas_h = 1360, 680
        canvas = np.zeros((canvas_h, canvas_w, 3), dtype=np.uint8)
        canvas[:] = (10, 14, 20)

        mirror_x, mirror_y = 25, 55
        mirror_w, mirror_h = 1310, 585

        # 상단 일체형 운전자 관찰 렌즈
        lens_cx, lens_cy, lens_r = 680, 50, 26
        cv2.circle(canvas, (lens_cx, lens_cy), lens_r + 4, (45, 60, 80), -1)
        cv2.circle(canvas, (lens_cx, lens_cy), lens_r, (15, 20, 25), -1)
        cv2.circle(canvas, (lens_cx, lens_cy), 12, (0, 140, 255), 2)
        cv2.circle(canvas, (lens_cx, lens_cy), 5, (0, 220, 255), -1)

        cv2.rectangle(canvas, (mirror_x, mirror_y), (mirror_x + mirror_w, mirror_y + mirror_h), (40, 55, 75), 4)

        w_side = 260
        h_side = 555
        side_y = 70

        x_left = 40
        x_right = 1060

        center_x = 315
        center_w = 730
        
        front_y = 70
        front_h = 135

        driver_y = 215
        driver_h = 260

        rear_y = 485
        rear_h = 140

        # 1. 왼쪽 카메라 (CH-2)
        v_left = np.zeros((h_side, w_side, 3), dtype=np.uint8)
        v_left[:] = (16, 22, 34)
        lx1 = int(75 - shift_ratio * 35)
        lx2 = int(175 - shift_ratio * 45)
        for y in range(int(road_offset) - 100, h_side + 100, 80):
            cv2.line(v_left, (lx1, y), (lx1, y + 40), (200, 220, 240), 2)
            cv2.line(v_left, (lx2, y), (lx2, y + 40), (200, 220, 240), 2)

        for v in left_traffic:
            vy = int(v.y)
            if -v.h < vy < h_side + 50:
                vx = int(22 if v.lane_col == 0 else 115)
                border_col = (0, 0, 255) if (150 < vy < 450) else v.border_color
                cv2.rectangle(v_left, (vx, vy), (vx + v.w, vy + v.h), v.color, -1)
                cv2.rectangle(v_left, (vx, vy), (vx + v.w, vy + v.h), border_col, 2)
                cv2.circle(v_left, (vx + 8, vy + v.h - 6), 3, (0, 0, 240), -1)
                cv2.circle(v_left, (vx + v.w - 8, vy + v.h - 6), 3, (0, 0, 240), -1)

        canvas[side_y:side_y + h_side, x_left:x_left + w_side] = v_left
        cv2.rectangle(canvas, (x_left, side_y), (x_left + w_side, side_y + h_side), (0, 130, 180), 2)

        # 2. 오른쪽 카메라 (CH-3)
        v_right = np.zeros((h_side, w_side, 3), dtype=np.uint8)
        if shift_ratio >= 0.70:
            v_right[:] = (26, 30, 38)
            for sy in range(-50, h_side + 50, 45):
                cv2.line(v_right, (15, sy), (80, sy + 30), (0, 170, 220), 2)
            cv2.line(v_right, (95, 0), (95, h_side), (0, 215, 255), 4)
            cv2.line(v_right, (145, 0), (145, h_side), (210, 220, 235), 8)
            for gy in range(0, h_side, 32):
                cv2.rectangle(v_right, (140, gy), (160, gy + 12), (130, 140, 160), -1)
                cv2.circle(v_right, (145, gy + 6), 3, (0, 100, 255), -1)
            cv2.rectangle(v_right, (165, 0), (w_side, h_side), (18, 26, 20), -1)
        else:
            v_right[:] = (16, 22, 34)
            rx1 = int(75 - shift_ratio * 70)
            rx2 = int(175 - shift_ratio * 90)
            for y in range(int(road_offset) - 100, h_side + 100, 80):
                cv2.line(v_right, (rx1, y), (rx1, y + 40), (200, 220, 240), 2)
                cv2.line(v_right, (rx2, y), (rx2, y + 40), (200, 220, 240), 2)
            rail_x = int(240 - shift_ratio * 85)
            cv2.line(v_right, (rail_x, 0), (rail_x, h_side), (180, 190, 205), 4)

            for v in right_traffic:
                vy = int(v.y)
                if -v.h < vy < h_side + 50:
                    vx = int(25 if v.lane_col == 0 else 115)
                    border_col = (0, 0, 255) if (150 < vy < 450) else v.border_color
                    cv2.rectangle(v_right, (vx, vy), (vx + v.w, vy + v.h), v.color, -1)
                    cv2.rectangle(v_right, (vx, vy), (vx + v.w, vy + v.h), border_col, 2)
                    cv2.circle(v_right, (vx + 6, vy + v.h - 5), 3, (0, 0, 240), -1)
                    cv2.circle(v_right, (vx + v.w - 6, vy + v.h - 5), 3, (0, 0, 240), -1)

        canvas[side_y:side_y + h_side, x_right:x_right + w_side] = v_right
        cv2.rectangle(canvas, (x_right, side_y), (x_right + w_side, side_y + h_side), (0, 130, 180), 2)

        # 3. 전방 카메라 (CH-4)
        v_front = np.zeros((front_h, center_w, 3), dtype=np.uint8)
        v_front[:] = (20, 26, 40)
        cv2.line(v_front, (0, 42), (center_w, 42), (45, 60, 85), 1)

        fx_center = int(center_w / 2 - (shift_ratio - 0.25) * 90)
        cv2.line(v_front, (fx_center - 40, 42), (fx_center - 190, front_h), (0, 255, 120), 2)
        cv2.line(v_front, (fx_center + 40, 42), (fx_center + 190, front_h), (0, 255, 120), 2)
        cv2.line(v_front, (fx_center - 80, 42), (fx_center - 330, front_h), (120, 140, 160), 1)
        cv2.line(v_front, (fx_center + 80, 42), (fx_center + 330, front_h), (120, 140, 160), 1)

        if shift_ratio > 0.4:
            fg_x = int(fx_center + 220)
            cv2.line(v_front, (fg_x - 30, 42), (fg_x + 30, front_h), (180, 190, 205), 4)

        if speed > 0:
            # (1) 전방 좌측 2차선 추월차
            fl_scale = max(0.4, min(1.0, 1.0 - (front_left_dist / 60.0)))
            fl_y = int(42 + fl_scale * 55)
            fl_w = int(24 * fl_scale)
            fl_x = int(fx_center - 90 - (1.0 - fl_scale) * 40)
            cv2.rectangle(v_front, (fl_x - fl_w, fl_y), (fl_x + fl_w, fl_y + int(24 * fl_scale)), (30, 40, 60), -1)
            cv2.rectangle(v_front, (fl_x - fl_w, fl_y), (fl_x + fl_w, fl_y + int(24 * fl_scale)), (80, 180, 240), 1)

            # (2) 전방 우측 4차선 트럭
            fr_scale = max(0.45, min(1.0, 1.0 - (front_right_dist / 50.0)))
            fr_y = int(42 + fr_scale * 55)
            fr_w = int(28 * fr_scale)
            fr_x = int(fx_center + 90 + (1.0 - fr_scale) * 40)
            cv2.rectangle(v_front, (fr_x - fr_w, fr_y), (fr_x + fr_w, fr_y + int(30 * fr_scale)), (50, 55, 65), -1)
            cv2.rectangle(v_front, (fr_x - fr_w, fr_y), (fr_x + fr_w, fr_y + int(30 * fr_scale)), (160, 170, 180), 1)

            # (3) 우리 차선 직전방 선행차 (감속 연동)
            f_scale = max(0.5, min(1.4, 1.0 + (32.0 - front_lead_dist) / 25.0))
            front_car_y = int(60 + (32.0 - front_lead_dist) * 1.6)
            front_car_w = int(32 * f_scale)
            front_car_h = int(38 * f_scale)
            f_box_col = (0, 0, 255) if front_brake_active else (100, 220, 255)
            cv2.rectangle(v_front, (fx_center - front_car_w, front_car_y), (fx_center + front_car_w, front_car_y + front_car_h), (40, 50, 70), -1)
            cv2.rectangle(v_front, (fx_center - front_car_w, front_car_y), (fx_center + front_car_w, front_car_y + front_car_h), f_box_col, 2)
            tail_col = (0, 0, 255) if front_brake_active else (0, 0, 180)
            cv2.circle(v_front, (fx_center - front_car_w + 8, front_car_y + front_car_h - 6), 4, tail_col, -1)
            cv2.circle(v_front, (fx_center + front_car_w - 8, front_car_y + front_car_h - 6), 4, tail_col, -1)

        canvas[front_y:front_y + front_h, center_x:center_x + center_w] = v_front
        cv2.rectangle(canvas, (center_x, front_y), (center_x + center_w, front_y + front_h), (0, 130, 180), 2)

        # 4. 운전자 관찰 카메라 DSM
        cam_resized = cv2.resize(cam_frame, (center_w, driver_h))
        canvas[driver_y:driver_y + driver_h, center_x:center_x + center_w] = cam_resized
        cv2.rectangle(canvas, (center_x, driver_y), (center_x + center_w, driver_y + driver_h), (0, 200, 255), 2)

        # -------------------------------------------------------------------------
        # 5. 🌟 [대표님 핵심 요청]: 후방카메라 (CH-5) - 앞차만큼 생생하게 움직이는 리얼 차량 렌더링!
        # -------------------------------------------------------------------------
        v_rear = np.zeros((rear_h, center_w, 3), dtype=np.uint8)
        v_rear[:] = (18, 24, 36)
        rx_center = int(center_w / 2 + (shift_ratio - 0.25) * 60)

        cv2.line(v_rear, (rx_center - 35, 25), (rx_center - 170, rear_h), (200, 220, 240), 2)
        cv2.line(v_rear, (rx_center + 35, 25), (rx_center + 170, rear_h), (200, 220, 240), 2)
        cv2.line(v_rear, (rx_center - 95, 75), (rx_center + 95, 75), (0, 255, 0), 2)   # 20m 안전
        cv2.line(v_rear, (rx_center - 75, 100), (rx_center + 75, 100), (0, 255, 255), 2) # 10m 주의
        cv2.line(v_rear, (rx_center - 55, 122), (rx_center + 55, 122), (0, 0, 255), 2)   # 5m 위험

        if state == "STOPPED":
            cone_pts = np.array([[rx_center - 18, 124], [rx_center + 18, 124], [rx_center, 86]], np.int32)
            cv2.fillPoly(v_rear, [cone_pts], (0, 120, 255))
            cv2.line(v_rear, (rx_center - 20, 126), (rx_center + 20, 126), (255, 255, 255), 3)
            cv2.circle(v_rear, (rx_center, 96), 4, (255, 255, 255), -1)

            cv2.rectangle(v_rear, (rx_center - 170, 38), (rx_center - 115, 75), (35, 75, 135), -1)
            cv2.rectangle(v_rear, (rx_center - 170, 38), (rx_center - 115, 75), (80, 160, 255), 1)
        else:
            # (1) 후방 좌측 본선 쌩쌩 달리는 차
            rl_scale = max(0.5, min(1.1, 1.0 - (rear_left_dist / 50.0)))
            rl_y = int(30 + rl_scale * 50)
            rl_w = int(25 * rl_scale)
            rl_x = int(rx_center - 115)
            cv2.rectangle(v_rear, (rl_x - rl_w, rl_y), (rl_x + rl_w, rl_y + int(30 * rl_scale)), (40, 50, 60), -1)
            cv2.rectangle(v_rear, (rl_x - rl_w, rl_y), (rl_x + rl_w, rl_y + int(30 * rl_scale)), (140, 200, 255), 1)
            cv2.circle(v_rear, (rl_x - rl_w + 6, rl_y + 6), 3, (100, 240, 255), -1)
            cv2.circle(v_rear, (rl_x + rl_w - 6, rl_y + 6), 3, (100, 240, 255), -1)

            # (2) 🌟 직후방 추종 차량 (앞차처럼 실시간으로 다가왔다 멀어지는 고도화 그래픽!)
            rc_scale = max(0.65, min(1.65, 1.0 + (22.0 - rear_lead_dist) / 16.0))
            rear_car_x = int(rx_center - rear_lead_offset_x)
            rear_car_y = int(45 + (22.0 - rear_lead_dist) * 2.2)
            rear_car_w = int(42 * rc_scale)
            rear_car_h = int(36 * rc_scale)

            car_body_col = (30, 48, 70) if not rear_tail_blink else (45, 55, 80)
            cv2.rectangle(v_rear, (rear_car_x - rear_car_w, rear_car_y), (rear_car_x + rear_car_w, rear_car_y + rear_car_h), car_body_col, -1)
            cv2.rectangle(v_rear, (rear_car_x - rear_car_w, rear_car_y), (rear_car_x + rear_car_w, rear_car_y + rear_car_h), (70, 150, 240), 2)

            ws_w = int(rear_car_w * 0.78)
            ws_h = int(rear_car_h * 0.42)
            cv2.rectangle(v_rear, (rear_car_x - ws_w, rear_car_y + 4), (rear_car_x + ws_w, rear_car_y + 4 + ws_h), (15, 22, 35), -1)
            cv2.rectangle(v_rear, (rear_car_x - ws_w, rear_car_y + 4), (rear_car_x + ws_w, rear_car_y + 4 + ws_h), (100, 180, 255), 1)

            sm_w = int(6 * rc_scale)
            sm_h = int(4 * rc_scale)
            cv2.rectangle(v_rear, (rear_car_x - rear_car_w - sm_w, rear_car_y + 10), (rear_car_x - rear_car_w, rear_car_y + 10 + sm_h), (50, 80, 120), -1)
            cv2.rectangle(v_rear, (rear_car_x + rear_car_w, rear_car_y + 10), (rear_car_x + rear_car_w + sm_w, rear_car_y + 10 + sm_h), (50, 80, 120), -1)

            grill_y = rear_car_y + ws_h + 8
            cv2.rectangle(v_rear, (rear_car_x - int(rear_car_w * 0.45), grill_y), (rear_car_x + int(rear_car_w * 0.45), grill_y + int(8 * rc_scale)), (10, 12, 16), -1)
            cv2.rectangle(v_rear, (rear_car_x - int(rear_car_w * 0.3), grill_y + 2), (rear_car_x + int(rear_car_w * 0.3), grill_y + int(7 * rc_scale)), (220, 220, 220), -1)

            hl_r = int(5 * rc_scale)
            hl_y = rear_car_y + ws_h + 6
            hl_left_x = rear_car_x - rear_car_w + int(10 * rc_scale)
            hl_right_x = rear_car_x + rear_car_w - int(10 * rc_scale)

            cv2.circle(v_rear, (hl_left_x, hl_y), hl_r + 4, (0, 180, 255), 1)
            cv2.circle(v_rear, (hl_right_x, hl_y), hl_r + 4, (0, 180, 255), 1)
            cv2.circle(v_rear, (hl_left_x, hl_y), hl_r, (180, 255, 255), -1)
            cv2.circle(v_rear, (hl_right_x, hl_y), hl_r, (180, 255, 255), -1)

        canvas[rear_y:rear_y + rear_h, center_x:center_x + center_w] = v_rear
        cv2.rectangle(canvas, (center_x, rear_y), (center_x + center_w, rear_y + rear_h), (0, 130, 180), 2)

        # 비상 시 전체 룸미러 테두리 붉은색 플래시 점멸
        if state in ["COUNTDOWN_5SEC", "EVADE_LANE_CHANGE", "EVADE_BRAKING", "STOPPED"]:
            blink = int((math.sin(now * 12) + 1) * 127)
            cv2.rectangle(canvas, (mirror_x, mirror_y), (mirror_x + mirror_w, mirror_y + mirror_h), (0, 0, blink), 5)

        # -------------------------------------------------------------------------
        # PIL 고대조 텍스트 및 카운트다운 OSD 렌더링
        # -------------------------------------------------------------------------
        pil_img = Image.fromarray(canvas)
        draw = ImageDraw.Draw(pil_img)

        draw.text((30, 8), "SafetyON™ All-in-One Electronic Digital Rearview Mirror", font=font_bold, fill=(56, 189, 248))
        draw.text((30, 26), "[특허 10건 공표 | 비상제동 0206816 우선심사 확정 | 반도체 0190435 우선심사결정]", font=font_micro, fill=(180, 230, 120))
        
        if left_turn_signal_state:
            draw.rectangle([(500, 8), (680, 44)], fill=(20, 140, 60), outline=(0, 255, 120), width=2)
            draw.text((510, 14), "[◀◀ 좌측 깜빡이 ON ▶▶]", font=font_bold, fill=(255, 255, 255))
        elif hazard_lamp_state:
            draw.rectangle([(500, 8), (680, 44)], fill=(220, 110, 0), outline=(255, 255, 0), width=2)
            draw.text((510, 14), "[◀◀ 비상등 점멸 ▶▶]", font=font_bold, fill=(255, 255, 255))
        elif front_brake_active:
            draw.rectangle([(480, 8), (700, 44)], fill=(180, 40, 20), outline=(255, 255, 0), width=2)
            draw.text((490, 14), f"[ADAS] 앞차 감속 감응 (-{abs(g_force):.2f}G)", font=font_bold, fill=(255, 255, 255))
        else:
            lane_str = f"주행:[{current_lane_f:.1f}차선]" if current_lane_f < 5.5 else "위치:[5차선 갓길정차]"
            draw.text((545, 16), lane_str, font=font_mid, fill=(255, 255, 255))

        draw.text((720, 16), f"속도:{speed:.1f}km/h", font=font_mid, fill=(100, 255, 100) if speed > 0 else (255, 100, 100))
        draw.text((830, 16), f"감속도:{g_force:.2f}G", font=font_mid, fill=(255, 200, 0) if g_force < 0 else (180, 190, 200))
        
        steer_color = (255, 150, 0) if steer_angle != 0 else (200, 230, 255)
        if steer_angle > 0:
            steer_str = f"조향: 우측 {steer_angle:.1f}°"
        elif steer_angle < 0:
            steer_str = f"조향: 좌측 {abs(steer_angle):.1f}°"
        else:
            steer_str = "조향: 0°"
        draw.text((945, 16), steer_str, font=font_mid, fill=steer_color)
        draw.text((1065, 16), f"가드레일:{guardrail_dist:.1f}m", font=font_mid, fill=(100, 220, 255))
        
        hr_col = (255, 50, 50) if heart_rate < 55 else (255, 130, 130)
        draw.text((1195, 16), f"심박:{heart_rate}bpm", font=font_mid, fill=hr_col)

        # [T] 5분 발표 스톱워치 타이머 OSD & [S] 오디오 배지
        if presentation_timer_start is not None:
            pt_elapsed = now - presentation_timer_start
            pt_min = int(pt_elapsed // 60)
            pt_sec = int(pt_elapsed % 60)
            pt_str = f"발표타이머 {pt_min:02d}:{pt_sec:02d} / 05:00"
            if pt_elapsed < 240:
                pt_col = (100, 255, 120)
            elif pt_elapsed < 285:
                pt_col = (255, 220, 50)
            else:
                pt_col = (255, 80, 80) if (int(now * 3.0) % 2 == 0) else (150, 0, 0)
            draw.rectangle([(320, 48), (490, 70)], fill=(15, 25, 40), outline=pt_col)
            draw.text((326, 52), pt_str, font=font_micro, fill=pt_col)

        # 오디오 음소거 상태 배지
        if sound_engine.is_muted:
            draw.rectangle([(500, 48), (580, 70)], fill=(60, 20, 20), outline=(255, 80, 80))
            draw.text((506, 52), "[MUTE 음소거]", font=font_micro, fill=(255, 150, 150))

        # 실시간 ECG 심전도 생체감시 펄스 파형 (특허 10-2026-0218523)
        ecg_x0, ecg_y0, ecg_w, ecg_h = 1275, 12, 65, 22
        draw.rectangle([(ecg_x0, ecg_y0), (ecg_x0 + ecg_w, ecg_y0 + ecg_h)], fill=(12, 22, 18), outline=(34, 197, 94))
        ecg_col = (34, 197, 94) if heart_rate >= 55 else (239, 68, 68)
        pts = []
        for px in range(ecg_w):
            phase = ((now * 2.8 + px * 0.055) % 1.0)
            if 0.44 < phase < 0.47:
                val = -3
            elif 0.47 <= phase < 0.52:
                val = 9
            elif 0.52 <= phase < 0.56:
                val = -5
            elif 0.65 < phase < 0.74:
                val = 3
            else:
                val = 0
            if heart_rate < 50:
                val = int(val * 0.25)
            pts.append((ecg_x0 + px, ecg_y0 + 11 - val))
        if len(pts) > 1:
            draw.line(pts, fill=ecg_col, width=2)

        # 1) 상단 렌즈 텍스트
        draw.text((715, 40), "운전자 관찰 카메라 ↗", font=font_bold, fill=(255, 255, 255))

        # 2) 왼쪽 카메라 라벨 & 차량 정보
        draw.rectangle([(x_left + 10, side_y + 10), (x_left + 250, side_y + 36)], fill=(15, 35, 55), outline=(0, 215, 255))
        draw.text((x_left + 85, side_y + 14), "왼쪽 카메라", font=font_bold, fill=(255, 255, 255))

        for v in left_traffic:
            vy = int(v.y)
            if 40 < vy < h_side - 30:
                vx = int(x_left + (22 if v.lane_col == 0 else 115))
                box_bg = (50, 15, 15) if (150 < vy < 450) else (15, 25, 40)
                box_ol = (255, 50, 50) if (150 < vy < 450) else v.border_color
                draw.rectangle([(vx, side_y + vy - 18), (vx + 110, side_y + vy)], fill=box_bg, outline=box_ol)
                tag_txt = f"[{v.vtype}] 접근주의!" if (150 < vy < 450) else f"[{v.vtype}] {v.plate}"
                draw.text((vx + 4, side_y + vy - 16), tag_txt, font=font_micro, fill=(255, 255, 255))

        # 3) 오른쪽 카메라 라벨 & 우측 차선 병합 안내 배너
        draw.rectangle([(x_right + 10, side_y + 10), (x_right + 250, side_y + 36)], fill=(15, 35, 55), outline=(0, 215, 255))
        draw.text((x_right + 80, side_y + 14), "오른쪽 카메라", font=font_bold, fill=(255, 255, 255))

        if right_merge_status:
            draw.rectangle([(x_right + 12, side_y + 45), (x_right + 248, side_y + 75)], fill=(20, 30, 50), outline=(255, 200, 0))
            draw.text((x_right + 16, side_y + 53), right_merge_status, font=font_micro, fill=(255, 220, 100))

        if shift_ratio >= 0.70:
            draw.rectangle([(x_right + 15, side_y + 240), (x_right + 245, side_y + 290)], fill=(15, 25, 35), outline=(0, 215, 255))
            draw.text((x_right + 35, side_y + 250), "우측 가드레일 1.2m 밀착", font=font_bold, fill=(100, 255, 100))
            draw.text((x_right + 42, side_y + 270), "통행 차량 0대 (안전 확보)", font=font_micro, fill=(200, 230, 255))
        else:
            for v in right_traffic:
                vy = int(v.y)
                if 40 < vy < h_side - 30:
                    vx = int(x_right + (25 if v.lane_col == 0 else 115))
                    box_bg = (50, 15, 15) if (150 < vy < 450) else (15, 25, 40)
                    box_ol = (255, 50, 50) if (150 < vy < 450) else v.border_color
                    if v.vtype == 'MOTO':
                        if vy < 220:
                            draw.rectangle([(vx - 10, side_y + vy - 20), (vx + 130, side_y + vy)], fill=(15, 40, 20), outline=(0, 255, 120))
                            draw.text((vx - 6, side_y + vy - 17), f"[MOTO] {v.plate} (후면인식)", font=font_micro, fill=(100, 255, 100))
                        else:
                            draw.rectangle([(vx - 10, side_y + vy - 20), (vx + 130, side_y + vy)], fill=box_bg, outline=box_ol)
                            draw.text((vx - 6, side_y + vy - 17), "[MOTO] 번호판 후면식별대기", font=font_micro, fill=(255, 200, 100))
                    else:
                        draw.rectangle([(vx, side_y + vy - 18), (vx + 110, side_y + vy)], fill=box_bg, outline=box_ol)
                        tag_txt = f"[{v.vtype}] 접근주의!" if (150 < vy < 450) else f"[{v.vtype}] {v.plate}"
                        draw.text((vx + 4, side_y + vy - 16), tag_txt, font=font_micro, fill=(255, 255, 255))

        # 4) 전방카메라 라벨 & 다중 차량 OSD
        draw.rectangle([(center_x + 10, front_y + 8), (center_x + center_w - 10, front_y + 32)], fill=(15, 35, 55), outline=(0, 255, 120))
        draw.text((center_x + int(center_w / 2) - 40, front_y + 11), "전방카메라", font=font_bold, fill=(255, 255, 255))
        if speed > 0:
            f_box_col = (255, 80, 80) if front_brake_active else (100, 220, 255)
            draw.rectangle([(center_x + 20, front_y + 40), (center_x + 230, front_y + 60)], fill=(15, 25, 40), outline=f_box_col)
            draw.text((center_x + 25, front_y + 43), f"[앞차] 45고 1234 ({front_lead_dist:.1f}m - 감속감응)", font=font_micro, fill=(255, 255, 255))
            draw.text((center_x + 245, front_y + 43), f"[2차로] {front_left_dist:.0f}m 앞", font=font_micro, fill=(150, 200, 255))
            draw.text((center_x + 480, front_y + 43), f"[4차로 트럭] {front_right_dist:.0f}m", font=font_micro, fill=(200, 220, 220))

        # 5) 운전자 관찰 카메라 DSM
        draw.rectangle([(center_x + 10, driver_y + 8), (center_x + 220, driver_y + 32)], fill=(15, 35, 55), outline=(0, 255, 120))
        draw.text((center_x + 18, driver_y + 11), "CH-1 운전자 안면/동공 DSM", font=font_small, fill=(0, 255, 120))

        # 🌟 5초 카운트다운 타이머 팝업 표출
        if state == "COUNTDOWN_5SEC":
            if countdown_reason == "두 눈 감김(졸음운전)":
                rem_sec = max(0.0, 10.0 - (now - eyes_closed_timer_start)) if eyes_closed_timer_start else 0.0
            else:
                rem_sec = max(0.0, 5.0 - (now - countdown_start_time))
            
            cb_x, cb_y, cb_w, cb_h = center_x + 30, driver_y + 35, center_w - 60, 185
            draw.rectangle([(cb_x, cb_y), (cb_x + cb_w, cb_y + cb_h)], fill=(25, 10, 15), outline=(255, 40, 40), width=3)
            draw.rectangle([(cb_x, cb_y), (cb_x + cb_w, cb_y + 35)], fill=(180, 20, 20))
            draw.text((cb_x + 45, cb_y + 6), f"🚨 [긴급 경고] 운전자 {countdown_reason} 감지!", font=font_bold, fill=(255, 255, 255))

            draw.text((cb_x + 85, cb_y + 50), "“5초 후 비상정차를 시도합니다.”", font=font_large, fill=(255, 220, 100))
            draw.text((cb_x + 130, cb_y + 85), f"비상 감속까지 남은 시간: {rem_sec:.1f}초", font=font_huge, fill=(255, 80, 80))

            bar_w = cb_w - 60
            prog_ratio = max(0.0, min(1.0, (5.0 - rem_sec) / 5.0))
            draw.rectangle([(cb_x + 30, cb_y + 130), (cb_x + 30 + bar_w, cb_y + 150)], fill=(40, 45, 55), outline=(200, 200, 200))
            draw.rectangle([(cb_x + 30, cb_y + 130), (cb_x + 30 + int(bar_w * prog_ratio), cb_y + 150)], fill=(255, 50, 50))

            draw.text((cb_x + 95, cb_y + 158), "※ 눈을 뜨거나 머리를 바로 세우면 즉시 비상정차가 취소됩니다.", font=font_micro, fill=(180, 220, 255))

        elif is_eyes_closed_frame and eyes_closed_timer_start:
            dur = now - eyes_closed_timer_start
            draw.rectangle([(center_x + 20, driver_y + driver_h - 40), (center_x + center_w - 20, driver_y + driver_h - 8)], fill=(180, 60, 0), outline=(255, 200, 0), width=2)
            draw.text((center_x + 60, driver_y + driver_h - 32), f"[주의] 두 눈 감김 감지! ({dur:.1f}초 / 10.0초 경과 시 갓길 비상정차 발동)", font=font_mid, fill=(255, 255, 255))
        elif head_abnormal:
            slump_type = "머리 푹 숙임(전방 전도)" if head_dropped else "뒤로 기절(후방 전도)"
            draw.rectangle([(center_x + 20, driver_y + driver_h - 40), (center_x + center_w - 20, driver_y + driver_h - 8)], fill=(180, 20, 20), outline=(255, 255, 0), width=2)
            draw.text((center_x + 75, driver_y + driver_h - 32), f"[비상] {slump_type} 실신 감지! -> 비상정차 시퀀스 가동", font=font_mid, fill=(255, 255, 255))
        elif hand_occlusion:
            draw.rectangle([(center_x + 20, driver_y + driver_h - 40), (center_x + center_w - 20, driver_y + driver_h - 8)], fill=(0, 65, 80), outline=(0, 220, 255), width=2)
            draw.text((center_x + 75, driver_y + driver_h - 32), "[정상] 머리/얼굴 손 가림 감지 -> 운전자 탑승 확인 (이탈 오경보 방지)", font=font_mid, fill=(255, 255, 255))
        elif face_detected:
            if pupil_open_ratio == 45:
                # 🌟 [한쪽 눈만 뜸/감김] 45% 개도율 및 황색 주의 박스!
                draw.rectangle([(center_x + 30, driver_y + driver_h - 40), (center_x + center_w - 30, driver_y + driver_h - 8)], fill=(110, 70, 0), outline=(255, 200, 0), width=2)
                draw.text((center_x + 100, driver_y + driver_h - 32), "[주의] 한쪽 눈 감김 감지 -> 주의력 저하 감시 (동공개도율 45%)", font=font_mid, fill=(255, 255, 255))
            else:
                # [두 눈 뜸] 95% 개도율 및 녹색 정상 박스!
                draw.rectangle([(center_x + 30, driver_y + driver_h - 40), (center_x + center_w - 30, driver_y + driver_h - 8)], fill=(0, 75, 50), outline=(0, 255, 150))
                draw.text((center_x + 105, driver_y + driver_h - 32), "[정상] 안면 및 양안 동공 감지 -> 안전 주행 유지 (동공개도율 95%)", font=font_mid, fill=(255, 255, 255))
            
            # 운전자 인증 배지
            draw.rectangle([(center_x + 350, driver_y + 10), (center_x + center_w - 15, driver_y + 32)], fill=(15, 30, 45), outline=(56, 189, 248))
            draw.text((center_x + 355, driver_y + 13), "인증: 변귀섭 대표이사 (생체감시 ON)", font=font_micro, fill=(180, 230, 255))
        else:
            draw.rectangle([(center_x + 40, driver_y + driver_h - 40), (center_x + center_w - 40, driver_y + driver_h - 8)], fill=(160, 20, 20), outline=(255, 50, 50))
            draw.text((center_x + 160, driver_y + driver_h - 32), "[비상] 운전자 이탈 감지!", font=font_mid, fill=(255, 255, 255))

        # 6) 후방카메라 라벨 & 뒤차 실시간 회피 추월 기동 OSD (앞차만큼 역동적)
        draw.rectangle([(center_x + 10, rear_y + 8), (center_x + center_w - 10, rear_y + 32)], fill=(15, 35, 55), outline=(0, 215, 255))
        draw.text((center_x + int(center_w / 2) - 40, rear_y + 11), "후방카메라", font=font_bold, fill=(255, 255, 255))
        # 후방 카메라 삼각콘 및 뒤차 상태 태그
        if speed <= 0.0:
            draw.rectangle([(center_x + center_w - 230, rear_y + 40), (center_x + center_w - 20, rear_y + 65)], fill=(180, 50, 0), outline=(255, 255, 0))
            draw.text((center_x + center_w - 220, rear_y + 45), "[안전 삼각콘 설치 완료]", font=font_small, fill=(255, 255, 255))

        if (current_lane_f <= 3.8) and (speed <= 0.0):
            # 🌟 3차선에서 우리 차가 정차했을 때 뒷차도 안전거리 8.5m에 정차 완료!
            rear_tag = f"[뒤차] {rear_lead_dist:.1f}m (3차선 비상정차 완료 | 2차 추돌 0건)"
            rear_box_col = (0, 255, 120)
        elif (current_lane_f <= 3.8) and (state in ["SUA_EMERGENCY", "BATTERY_EMERGENCY"] or front_brake_active):
            rear_tag = f"[뒤차] {rear_lead_dist:.1f}m (비상 감속 정차 유도 중)"
            rear_box_col = (255, 200, 0)
        elif rear_lead_offset_x > 20:
            rear_tag = f"[뒤차] {rear_lead_dist:.1f}m (좌측 회피 추월 중)"
            rear_box_col = (255, 100, 100)
        else:
            rear_tag = f"[뒤차] {rear_lead_dist:.1f}m (추종 주행 중)"
            rear_box_col = (80, 160, 255)

        draw.rectangle([(center_x + 20, rear_y + 40), (center_x + 300, rear_y + 60)], fill=(15, 25, 40), outline=rear_box_col)
        draw.text((center_x + 25, rear_y + 43), rear_tag, font=font_micro, fill=(200, 230, 255))
        draw.text((center_x + 480, rear_y + 43), f"[후방 좌측차] {rear_left_dist:.0f}m", font=font_micro, fill=(150, 220, 255))

        # 7) 하단 대화면 인터랙티브 컨트롤 독 (독립 바, 텍스트 겹침 0%)
        dock_y0, dock_y1 = 643, 674
        draw.rectangle([(25, dock_y0), (1335, dock_y1)], fill=(12, 18, 28), outline=(45, 65, 90), width=1)

        # 8대 단축키 버튼 슬롯 렌더링 (마우스 클릭 및 키보드 직관 안내)
        btn_slots = [
            (32, 175, "SPACE: 기절/비상정차", (239, 68, 68), (185, 28, 28)),
            (182, 335, "A: 급발진 150kgf 제동", (245, 158, 11), (180, 83, 9)),
            (342, 485, "F: 침수 도어유리파쇄", (56, 189, 248), (2, 132, 199)),
            (492, 640, "B: EV배터리 방호", (168, 85, 247), (126, 34, 206)),
            (647, 765, "L: 좌측회피 추월", (34, 197, 94), (22, 101, 52)),
            (772, 875, "TAB: 전체화면", (14, 165, 233), (3, 105, 161)),
            (880, 965, "T: 5분타이머", (45, 212, 191), (15, 118, 110)),
            (970, 1050, "S: 음소거", (251, 146, 60), (194, 65, 12)),
            (1055, 1135, "R: 전체리셋", (234, 179, 8), (161, 98, 7)),
            (1140, 1210, "Q: 종료", (148, 163, 184), (71, 85, 105)),
        ]
        for bx0, bx1, blabel, bcol, bfill in btn_slots:
            draw.rectangle([(bx0, dock_y0 + 3), (bx1, dock_y1 - 3)], fill=(20, 28, 42), outline=bcol, width=1)
            draw.text((bx0 + 5, dock_y0 + 7), blabel, font=font_micro, fill=bcol)

        draw.text((1220, dock_y0 + 7), "SafetyON CMS/DSM", font=font_micro, fill=(200, 225, 255))

        # ---------------- 3자 동시 긴급구난 e-Call 패널 ----------------
        if state in ["EVADE_LANE_CHANGE", "EVADE_BRAKING", "STOPPED"]:
            bx, by, bw, bh = 345, 100, 670, 360
            draw.rectangle([(bx, by), (bx + bw, by + bh)], fill=(15, 20, 32), outline=(255, 80, 80), width=3)
            draw.rectangle([(bx, by), (bx + bw, by + 40)], fill=(180, 20, 20))

            if state == "EVADE_LANE_CHANGE":
                phase_title = "[비상 정차 1단계] 우측 통행차량 안전 확인 후 갓길 차선변경 중"
            elif state == "EVADE_BRAKING":
                phase_title = "[비상 정차 2단계] 최우측 갓길 1.2m 밀착 0.22G 다단 감속 중"
            else:
                phase_title = "[비상 정차 완료] 최우측 갓길 정차 완료 및 3자 동시 e-Call 구난 가동"

            draw.text((bx + 20, by + 10), phase_title, font=font_bold, fill=(255, 255, 255))

            card_y = by + 55
            card_w = 205
            card_h = 200

            # [1] 소방청 119
            c1_x = bx + 12
            draw.rectangle([(c1_x, card_y), (c1_x + card_w, card_y + card_h)], fill=(25, 15, 20), outline=(239, 68, 68), width=2)
            draw.rectangle([(c1_x, card_y), (c1_x + card_w, card_y + 26)], fill=(185, 28, 28))
            draw.text((c1_x + 8, card_y + 5), "119 소방청 긴급출동", font=font_bold, fill=(255, 255, 255))
            draw.text((c1_x + 8, card_y + 35), "• 상태: 자동 핫라인 연결 완료", font=font_small, fill=(255, 100, 100))
            for wi in range(6):
                wh = int(random.uniform(4, 16))
                draw.line([(c1_x + 149 + wi * 8, card_y + 44 - wh // 2), (c1_x + 149 + wi * 8, card_y + 44 + wh // 2)], fill=(0, 255, 120))
            draw.text((c1_x + 8, card_y + 60), "• 위치: 경부선 382km 하행", font=font_micro, fill=(220, 220, 220))
            draw.text((c1_x + 8, card_y + 78), f"  (GPS: {gps_lat:.4f}, {gps_lon:.4f})", font=font_micro, fill=(150, 220, 255))
            draw.text((c1_x + 8, card_y + 98), f"• 환자: 의식소실(심박 {heart_rate}bpm)", font=font_micro, fill=(255, 180, 180))
            draw.text((c1_x + 8, card_y + 116), "• 승객: 34명 안전 갓길정차", font=font_micro, fill=(200, 255, 200))
            draw.rectangle([(c1_x + 8, card_y + 150), (c1_x + card_w - 8, card_y + 190)], fill=(60, 20, 20), outline=(255, 100, 100))
            draw.text((c1_x + 18, card_y + 160), "구급차 출동 중 (3분 후 도착)", font=font_small, fill=(255, 255, 100))

            # [2] 운송사
            c2_x = bx + 230
            draw.rectangle([(c2_x, card_y), (c2_x + card_w, card_y + card_h)], fill=(15, 25, 40), outline=(56, 189, 248), width=2)
            draw.rectangle([(c2_x, card_y), (c2_x + card_w, card_y + 26)], fill=(2, 132, 199))
            draw.text((c2_x + 8, card_y + 5), "운송회사 중앙관제실", font=font_bold, fill=(255, 255, 255))
            draw.text((c2_x + 8, card_y + 35), "• 상태: 관제 채널 LIVE 연결", font=font_small, fill=(56, 189, 248))
            draw.text((c2_x + 8, card_y + 60), "• 차량: 경기70아 1234호", font=font_micro, fill=(220, 220, 220))
            draw.text((c2_x + 8, card_y + 78), "• 5채널 영상: 실시간 전송 중", font=font_micro, fill=(180, 230, 255))
            draw.text((c2_x + 8, card_y + 98), "• 도어 상태: 비상 자동 언락", font=font_micro, fill=(100, 255, 100))
            draw.text((c2_x + 8, card_y + 116), "• 후속 대책: 대체 버스 배차", font=font_micro, fill=(255, 220, 150))
            draw.rectangle([(c2_x + 8, card_y + 150), (c2_x + card_w - 8, card_y + 190)], fill=(12, 45, 75), outline=(56, 189, 248))
            draw.text((c2_x + 22, card_y + 160), "관제팀 긴급대응 승인 완료", font=font_small, fill=(100, 255, 255))

            # [3] 가족
            c3_x = bx + 448
            draw.rectangle([(c3_x, card_y), (c3_x + card_w, card_y + card_h)], fill=(15, 35, 25), outline=(34, 197, 94), width=2)
            draw.rectangle([(c3_x, card_y), (c3_x + card_w, card_y + 26)], fill=(22, 101, 52))
            draw.text((c3_x + 8, card_y + 5), "가족/지인 안심 SMS", font=font_bold, fill=(255, 255, 255))
            draw.text((c3_x + 8, card_y + 35), "• 상태: 긴급 문자 발송 완료", font=font_small, fill=(74, 222, 128))
            draw.text((c3_x + 8, card_y + 60), "• 수신: 010-5121-1353 (가족/대표)", font=font_micro, fill=(220, 220, 220))
            draw.text((c3_x + 8, card_y + 78), "• 내용: [세이프티온 안심문자]", font=font_micro, fill=(180, 255, 180))
            draw.text((c3_x + 8, card_y + 98), f"  '기사님 {countdown_reason} 감지되어", font=font_micro, fill=(255, 255, 200))
            draw.text((c3_x + 8, card_y + 116), "  갓길 안전정차. 119 출동 중'", font=font_micro, fill=(255, 255, 200))
            draw.rectangle([(c3_x + 8, card_y + 150), (c3_x + card_w - 8, card_y + 190)], fill=(15, 50, 30), outline=(34, 197, 94))
            draw.text((c3_x + 28, card_y + 160), "위치 지도 링크 전송 완료", font=font_small, fill=(150, 255, 150))

            draw.text((bx + 25, by + 270), "※ 바탕화면에 [세이프티온_비상긴급호출_전송로그.txt] 공식 전송 기록 생성 완료 [저장]", font=font_small, fill=(200, 230, 255))

            draw.rectangle([(bx + 245, by + 305), (bx + 425, by + 345)], fill=(40, 50, 75), outline=(200, 220, 255), width=2)
            draw.text((bx + 267, by + 316), "키보드 [ R ] 누르면 리셋", font=font_bold, fill=(255, 255, 255))

        
        # ---------------- 침수 시 도어 글래스 자동 파쇄 OSD ----------------
        if state == "FLOOD_EMERGENCY":
            fbx, fby, fbw, fbh = 320, 85, 720, 390
            draw.rectangle([(fbx, fby), (fbx + fbw, fby + fbh)], fill=(10, 22, 38), outline=(0, 220, 255), width=3)
            draw.rectangle([(fbx, fby), (fbx + fbw, fby + 42)], fill=(12, 74, 110))

            f_title = f"[차량 침수 비상 탈출] 수위 {flood_water_level:.1f}cm 감지 -> 도어 글래스 0.05초 자동 파쇄 격발!"
            draw.text((fbx + 20, fby + 11), f_title, font=font_bold, fill=(255, 255, 255))

            f_card_y = fby + 58
            f_card_w = 222
            f_card_h = 225

            # [카드 1] 침수 감지 센서
            fc1_x = fbx + 12
            draw.rectangle([(fc1_x, f_card_y), (fc1_x + f_card_w, f_card_y + f_card_h)], fill=(15, 30, 48), outline=(56, 189, 248), width=2)
            draw.rectangle([(fc1_x, f_card_y), (fc1_x + f_card_w, f_card_y + 26)], fill=(3, 105, 161))
            draw.text((fc1_x + 8, f_card_y + 5), "차량 침수 수위 센서", font=font_bold, fill=(255, 255, 255))
            draw.text((fc1_x + 8, f_card_y + 35), "• 상태: 바닥/도어 침수 100% 감지", font=font_micro, fill=(100, 255, 220))
            draw.text((fc1_x + 8, f_card_y + 58), f"• 실시간 침수위: {flood_water_level:.1f} cm", font=font_bold, fill=(255, 220, 100))
            draw.text((fc1_x + 8, f_card_y + 82), "• 외부 수압: 145 kgf (도어 개폐 불가)", font=font_micro, fill=(255, 120, 120))
            draw.text((fc1_x + 8, f_card_y + 104), "• 전원: 고전압 배터리 컷오프 완료", font=font_micro, fill=(200, 230, 255))
            draw.text((fc1_x + 8, f_card_y + 126), "• 위치: 침수 위험 지하차도", font=font_micro, fill=(180, 220, 255))
            draw.rectangle([(fc1_x + 8, f_card_y + 165), (fc1_x + f_card_w - 8, f_card_y + 215)], fill=(12, 45, 75), outline=(56, 189, 248))
            draw.text((fc1_x + 16, f_card_y + 175), "수압 차단 한계 돌파", font=font_small, fill=(255, 200, 100))
            draw.text((fc1_x + 16, f_card_y + 193), "즉각 비상 파쇄 승인", font=font_small, fill=(100, 255, 200))

            # [카드 2] 도어 글래스 자동 파쇄 펀칭 모듈
            fc2_x = fbx + 248
            draw.rectangle([(fc2_x, f_card_y), (fc2_x + f_card_w, f_card_y + f_card_h)], fill=(40, 20, 20), outline=(239, 68, 68), width=2)
            draw.rectangle([(fc2_x, f_card_y), (fc2_x + f_card_w, f_card_y + 26)], fill=(185, 28, 28))
            draw.text((fc2_x + 8, f_card_y + 5), "유리 자동 파쇄 펀칭 모듈", font=font_bold, fill=(255, 255, 255))
            draw.text((fc2_x + 8, f_card_y + 35), "• 특허: 10-2026-0221195 펀처", font=font_micro, fill=(255, 150, 150))
            draw.text((fc2_x + 8, f_card_y + 58), "• 펀치 격발: 0.05초 초고속 격발!", font=font_bold, fill=(255, 100, 100))
            draw.text((fc2_x + 8, f_card_y + 82), "• 대상: 운전석/조수석 4개 창문", font=font_micro, fill=(255, 200, 200))
            draw.text((fc2_x + 8, f_card_y + 104), "• 탈출로: 골든타임 100% 확보", font=font_bold, fill=(100, 255, 100))
            draw.text((fc2_x + 8, f_card_y + 126), "• 전원: 방수 캡슐 백업 배터리", font=font_micro, fill=(200, 230, 255))
            draw.rectangle([(fc2_x + 8, f_card_y + 165), (fc2_x + f_card_w - 8, f_card_y + 215)], fill=(65, 20, 20), outline=(239, 68, 68))
            draw.text((fc2_x + 16, f_card_y + 175), "도어 창문 파쇄 완료!", font=font_small, fill=(255, 255, 100))
            draw.text((fc2_x + 16, f_card_y + 193), "창문으로 즉시 탈출 가능", font=font_small, fill=(150, 255, 150))

            # [카드 3] 119 수난구조대 & 해경 e-Call
            fc3_x = fbx + 484
            draw.rectangle([(fc3_x, f_card_y), (fc3_x + f_card_w, f_card_y + f_card_h)], fill=(15, 35, 25), outline=(34, 197, 94), width=2)
            draw.rectangle([(fc3_x, f_card_y), (fc3_x + f_card_w, f_card_y + 26)], fill=(22, 101, 52))
            draw.text((fc3_x + 8, f_card_y + 5), "119 수난구조 특수팀", font=font_bold, fill=(255, 255, 255))
            draw.text((fc3_x + 8, f_card_y + 35), "• 상태: 침수 조난 e-Call 전송 완료", font=font_micro, fill=(100, 255, 150))
            draw.text((fc3_x + 8, f_card_y + 58), f"• 침수위치: GPS({gps_lat:.4f}, {gps_lon:.4f})", font=font_micro, fill=(150, 220, 255))
            draw.text((fc3_x + 8, f_card_y + 82), "• 차량: 경기70아 1234호 (침수)", font=font_micro, fill=(220, 220, 220))
            draw.text((fc3_x + 8, f_card_y + 104), "• 탑승자: 4명 침수 고립 탈출 중", font=font_micro, fill=(255, 220, 150))
            draw.text((fc3_x + 8, f_card_y + 126), "• 비콘: 루프탑 방수 비콘 점멸", font=font_micro, fill=(200, 255, 200))
            draw.rectangle([(fc3_x + 8, f_card_y + 165), (fc3_x + f_card_w - 8, f_card_y + 215)], fill=(15, 50, 30), outline=(34, 197, 94))
            draw.text((fc3_x + 16, f_card_y + 175), "수난구조 특수팀 출동", font=font_small, fill=(255, 255, 100))
            draw.text((fc3_x + 16, f_card_y + 193), "보트/잠수조 급파 완료", font=font_small, fill=(150, 255, 150))

            draw.text((fbx + 25, fby + 300), "※ 바탕화면에 [세이프티온_침수탈출_긴급구조_로그.txt] 공식 전송 기록 생성 완료 [저장]", font=font_small, fill=(200, 230, 255))

            draw.rectangle([(fbx + 265, fby + 335), (fbx + 455, fby + 375)], fill=(20, 45, 75), outline=(0, 220, 255), width=2)
            draw.text((fbx + 285, fby + 346), "키보드 [ R ] 누르면 리셋", font=font_bold, fill=(255, 255, 255))

        # ---------------- 급발진 차단 & 150kgf 비상 제동 OSD ----------------
        if state == "SUA_EMERGENCY":
            abx, aby, abw, abh = 320, 85, 720, 390
            draw.rectangle([(abx, aby), (abx + abw, aby + abh)], fill=(25, 12, 12), outline=(255, 60, 60), width=3)
            draw.rectangle([(abx, aby), (abx + abw, aby + 42)], fill=(185, 28, 28))

            a_title = f"[급발진 비상 제동] 가속페달 오조작 감지 -> 엔진 전원 컷오프 & 150kgf 강제 제동!"
            draw.text((abx + 20, aby + 11), a_title, font=font_bold, fill=(255, 255, 255))

            a_card_y = aby + 58
            a_card_w = 222
            a_card_h = 225

            # [카드 1] 페달 오조작 / 급발진 감지
            ac1_x = abx + 12
            draw.rectangle([(ac1_x, a_card_y), (ac1_x + a_card_w, a_card_y + a_card_h)], fill=(35, 15, 15), outline=(239, 68, 68), width=2)
            draw.rectangle([(ac1_x, a_card_y), (ac1_x + a_card_w, a_card_y + 26)], fill=(153, 27, 27))
            draw.text((ac1_x + 8, a_card_y + 5), "급발진·페달오조작 센서", font=font_bold, fill=(255, 255, 255))
            draw.text((ac1_x + 8, a_card_y + 35), "• 상태: 비정상 급가속 100% 감지", font=font_micro, fill=(255, 150, 150))
            draw.text((ac1_x + 8, a_card_y + 58), f"• 현재속도: {speed:.1f} km/h (이상치)", font=font_bold, fill=(255, 220, 100))
            draw.text((ac1_x + 8, a_card_y + 82), "• 가속페달: 98% 급격 개도 감지", font=font_micro, fill=(255, 180, 180))
            draw.text((ac1_x + 8, a_card_y + 104), "• 전방추돌: 위험도 최고치(CRITICAL)", font=font_micro, fill=(255, 100, 100))
            draw.text((ac1_x + 8, a_card_y + 126), "• 판정: 즉각 비상 제동 승인", font=font_micro, fill=(180, 255, 180))
            draw.rectangle([(ac1_x + 8, a_card_y + 165), (ac1_x + a_card_w - 8, a_card_y + 215)], fill=(65, 20, 20), outline=(239, 68, 68))
            draw.text((ac1_x + 16, a_card_y + 175), "가속 오조작 확정 판정", font=font_small, fill=(255, 200, 100))
            draw.text((ac1_x + 16, a_card_y + 193), "비상 개입 시스템 가동", font=font_small, fill=(100, 255, 200))

            # [카드 2] 엔진/모터 물리 전원 컷오프
            ac2_x = abx + 248
            draw.rectangle([(ac2_x, a_card_y), (ac2_x + a_card_w, a_card_y + a_card_h)], fill=(30, 20, 10), outline=(245, 158, 11), width=2)
            draw.rectangle([(ac2_x, a_card_y), (ac2_x + a_card_w, a_card_y + 26)], fill=(180, 83, 9))
            draw.text((ac2_x + 8, a_card_y + 5), "[특허 1단계] 엔진 물리 컷오프", font=font_bold, fill=(255, 255, 255))
            draw.text((ac2_x + 8, a_card_y + 35), "• 특허: 10-2026-0206816", font=font_micro, fill=(255, 220, 150))
            draw.text((ac2_x + 8, a_card_y + 58), "• 동력차단: 0.1초 내 전원 컷오프!", font=font_bold, fill=(255, 220, 100))
            draw.text((ac2_x + 8, a_card_y + 82), "• 구동모터: 출력 0.0 kW 차단", font=font_micro, fill=(200, 255, 200))
            draw.text((ac2_x + 8, a_card_y + 104), "• ECU바이패스: 물리 릴레이 개방", font=font_micro, fill=(220, 220, 255))
            draw.text((ac2_x + 8, a_card_y + 126), "• 동력 전달: 100% 완전 소멸", font=font_micro, fill=(150, 255, 150))
            draw.rectangle([(ac2_x + 8, a_card_y + 165), (ac2_x + a_card_w - 8, a_card_y + 215)], fill=(60, 35, 10), outline=(245, 158, 11))
            draw.text((ac2_x + 16, a_card_y + 175), "엔진/모터 물리 전원 컷", font=font_small, fill=(255, 255, 100))
            draw.text((ac2_x + 16, a_card_y + 193), "가속력 0.0kW 강제 소멸", font=font_small, fill=(150, 255, 150))

            # [카드 3] 2층 시소반전 150kgf 가압 모듈
            ac3_x = abx + 484
            draw.rectangle([(ac3_x, a_card_y), (ac3_x + a_card_w, a_card_y + a_card_h)], fill=(15, 30, 20), outline=(34, 197, 94), width=2)
            draw.rectangle([(ac3_x, a_card_y), (ac3_x + a_card_w, a_card_y + 26)], fill=(22, 101, 52))
            draw.text((ac3_x + 8, a_card_y + 5), "[특허 2단계] 150kgf 물리 제동", font=font_bold, fill=(255, 255, 255))
            draw.text((ac3_x + 8, a_card_y + 35), "• 메커니즘: 2층 시소반전 푸시로드", font=font_micro, fill=(150, 255, 180))
            draw.text((ac3_x + 8, a_card_y + 58), "• 페달 가압력: 150 kgf 직결 가압!", font=font_bold, fill=(100, 255, 150))
            draw.text((ac3_x + 8, a_card_y + 82), "• 진공상실 극복: 기계식 100% 가압", font=font_micro, fill=(220, 255, 220))
            draw.text((ac3_x + 8, a_card_y + 104), f"• 감속도: {g_force:.2f}G 안전 다단 정차", font=font_bold, fill=(255, 220, 100))
            draw.text((ac3_x + 8, a_card_y + 126), "• 안전확보: 2차 추돌사고 0건", font=font_micro, fill=(200, 255, 200))
            draw.rectangle([(ac3_x + 8, a_card_y + 165), (ac3_x + a_card_w - 8, a_card_y + 215)], fill=(15, 50, 25), outline=(34, 197, 94))
            draw.text((ac3_x + 16, a_card_y + 175), "150kgf 물리 제동 완료", font=font_small, fill=(255, 255, 100))
            draw.text((ac3_x + 16, a_card_y + 193), "안전 정차 성공 (0 km/h)", font=font_small, fill=(150, 255, 150))

            draw.text((abx + 25, aby + 300), "※ 바탕화면에 [세이프티온_급발진차단_제동로그.txt] 공식 기록 생성 완료 [저장]", font=font_small, fill=(200, 230, 255))
            draw.rectangle([(abx + 265, aby + 335), (abx + 455, aby + 375)], fill=(20, 45, 75), outline=(0, 220, 255), width=2)
            draw.text((abx + 285, aby + 346), "키보드 [ R ] 누르면 리셋", font=font_bold, fill=(255, 255, 255))

        # ---------------- 전기차(EV) 배터리팩 하부 충돌 & 화재 방호 OSD ----------------
        if state == "BATTERY_EMERGENCY":
            bbx, bby, bbw, bbh = 320, 85, 720, 390
            draw.rectangle([(bbx, bby), (bbx + bbw, bby + bbh)], fill=(12, 20, 35), outline=(56, 189, 248), width=3)
            draw.rectangle([(bbx, bby), (bbx + bbw, bby + 42)], fill=(3, 105, 161))

            b_title = f"[EV 배터리 방호] 하부 파편 충돌 감지 -> STF 쉴드 경화 & 자가밀폐 젤 0.05초 봉합!"
            draw.text((bbx + 20, bby + 11), b_title, font=font_bold, fill=(255, 255, 255))

            b_card_y = bby + 58
            b_card_w = 222
            b_card_h = 225

            # [카드 1] 노면 충격 센서
            bc1_x = bbx + 12
            draw.rectangle([(bc1_x, b_card_y), (bc1_x + b_card_w, b_card_y + b_card_h)], fill=(15, 25, 40), outline=(56, 189, 248), width=2)
            draw.rectangle([(bc1_x, b_card_y), (bc1_x + b_card_w, b_card_y + 26)], fill=(2, 132, 199))
            draw.text((bc1_x + 8, b_card_y + 5), "하부 충격 감지 센서", font=font_bold, fill=(255, 255, 255))
            draw.text((bc1_x + 8, b_card_y + 35), "• 상태: 노면 돌기·파편 충돌 감지", font=font_micro, fill=(100, 255, 220))
            draw.text((bc1_x + 8, b_card_y + 58), "• 충격 에너지: 180 J (고에너지)", font=font_bold, fill=(255, 220, 100))
            draw.text((bc1_x + 8, b_card_y + 82), f"• 배터리 온도: {battery_temp:.1f} ℃ (안정)", font=font_micro, fill=(150, 220, 255))
            draw.text((bc1_x + 8, b_card_y + 104), "• 관통 위험: Level 3 고위험 감지", font=font_micro, fill=(255, 150, 150))
            draw.text((bc1_x + 8, b_card_y + 126), "• 판정: 즉각 다중 방어막 가동", font=font_micro, fill=(180, 255, 180))
            draw.rectangle([(bc1_x + 8, b_card_y + 165), (bc1_x + b_card_w - 8, b_card_y + 215)], fill=(12, 45, 75), outline=(56, 189, 248))
            draw.text((bc1_x + 16, b_card_y + 175), "하부 충격파 즉각 감지", font=font_small, fill=(255, 200, 100))
            draw.text((bc1_x + 16, b_card_y + 193), "3중 안전 방어벽 승인", font=font_small, fill=(100, 255, 200))

            # [카드 2] 전단농화 복합체 & 자가밀폐 젤
            bc2_x = bbx + 248
            draw.rectangle([(bc2_x, b_card_y), (bc2_x + b_card_w, b_card_y + b_card_h)], fill=(15, 35, 30), outline=(16, 185, 129), width=2)
            draw.rectangle([(bc2_x, b_card_y), (bc2_x + b_card_w, b_card_y + 26)], fill=(5, 150, 105))
            draw.text((bc2_x + 8, b_card_y + 5), "[특허 1단계] STF쉴드 & 자가밀폐", font=font_bold, fill=(255, 255, 255))
            draw.text((bc2_x + 8, b_card_y + 35), "• 특허: 10-2026-0227055", font=font_micro, fill=(150, 255, 200))
            draw.text((bc2_x + 8, b_card_y + 58), "• STF 쉴드: 충격 순간 강철 경화!", font=font_bold, fill=(100, 255, 150))
            draw.text((bc2_x + 8, b_card_y + 82), "• 자가밀폐 젤: 0.05초 즉각 봉합", font=font_micro, fill=(220, 255, 220))
            draw.text((bc2_x + 8, b_card_y + 104), "• 방수/방기: 수분·공기 침투 차단", font=font_micro, fill=(200, 230, 255))
            draw.text((bc2_x + 8, b_card_y + 126), "• 셀 보호율: 내부 셀 손상률 0%", font=font_bold, fill=(255, 255, 100))
            draw.rectangle([(bc2_x + 8, b_card_y + 165), (bc2_x + b_card_w - 8, b_card_y + 215)], fill=(15, 50, 35), outline=(16, 185, 129))
            draw.text((bc2_x + 16, b_card_y + 175), "STF 관통 저지 100%", font=font_small, fill=(255, 255, 100))
            draw.text((bc2_x + 16, b_card_y + 193), "미세 균열 자가 치유 완료", font=font_small, fill=(150, 255, 150))

            # [카드 3] 열팽창 흑연 방화 격벽
            bc3_x = bbx + 484
            draw.rectangle([(bc3_x, b_card_y), (bc3_x + b_card_w, b_card_y + b_card_h)], fill=(25, 20, 35), outline=(168, 85, 247), width=2)
            draw.rectangle([(bc3_x, b_card_y), (bc3_x + b_card_w, b_card_y + 26)], fill=(126, 34, 206))
            draw.text((bc3_x + 8, b_card_y + 5), "[특허 2단계] 열팽창 방화벽 격리", font=font_bold, fill=(255, 255, 255))
            draw.text((bc3_x + 8, b_card_y + 35), "• 셀 격벽: 열팽창 흑연 300% 팽창", font=font_micro, fill=(220, 180, 255))
            draw.text((bc3_x + 8, b_card_y + 58), "• 열폭주(Runaway): 원천 차단!", font=font_bold, fill=(255, 200, 100))
            draw.text((bc3_x + 8, b_card_y + 82), "• 고전압 릴레이: 0.02초 컷오프", font=font_micro, fill=(200, 220, 255))
            draw.text((bc3_x + 8, b_card_y + 104), "• 인접 셀 전파: 화재 확산 0%", font=font_micro, fill=(150, 255, 150))
            draw.text((bc3_x + 8, b_card_y + 126), "• 안전 정차: 감속 유도 및 승객 보호", font=font_micro, fill=(220, 255, 220))
            draw.rectangle([(bc3_x + 8, b_card_y + 165), (bc3_x + b_card_w - 8, b_card_y + 215)], fill=(45, 20, 60), outline=(168, 85, 247))
            draw.text((bc3_x + 16, b_card_y + 175), "열폭주 연쇄 반응 차단", font=font_small, fill=(255, 255, 100))
            draw.text((bc3_x + 16, b_card_y + 193), "전기차 화재 원천 방지", font=font_small, fill=(150, 255, 150))

            draw.text((bbx + 25, bby + 300), "※ 바탕화면에 [세이프티온_전기차배터리방호_로그.txt] 공식 기록 생성 완료 [저장]", font=font_small, fill=(200, 230, 255))
            draw.rectangle([(bbx + 265, bby + 335), (bbx + 455, bby + 375)], fill=(20, 45, 75), outline=(0, 220, 255), width=2)
            draw.text((bbx + 285, bby + 346), "키보드 [ R ] 누르면 리셋", font=font_bold, fill=(255, 255, 255))

        canvas = np.array(pil_img)
        cv2.imshow(win_name, canvas)

        key = cv2.waitKey(20) & 0xFF
        if mouse_cmd_queue:
            m_cmd = mouse_cmd_queue.pop(0)
            if m_cmd == ' ':
                key = ord(' ')
            elif m_cmd == '	':
                key = 9
            else:
                key = ord(m_cmd)

        if key == ord('q') or key == 27:
            break
        elif key == ord('l') or key == ord('L'):
            if state in ["NORMAL", "COUNTDOWN_5SEC"]:
                state = "EVADE_LEFT_PASS"
                left_evade_start_time = now
        elif key == ord('f') or key == ord('F'):
            if state != "FLOOD_EMERGENCY":
                state = "FLOOD_EMERGENCY"
                flood_start_time = now
                flood_water_level = 15.0
                sound_engine.play_hazard_beep()
                sound_engine.play_119_siren()
                sound_engine.play_voice_flood()
                log_flood_dispatch(gps_lat, gps_lon, "정선/삼척 침수위험 지하차도")
        elif key == ord('a') or key == ord('A'):
            if state != "SUA_EMERGENCY":
                state = "SUA_EMERGENCY"
                sua_start_time = now
                sound_engine.play_hazard_beep()
                sound_engine.play_voice_sua()
        elif key == ord('b') or key == ord('B'):
            if state != "BATTERY_EMERGENCY":
                state = "BATTERY_EMERGENCY"
                battery_start_time = now
                sound_engine.play_hazard_beep()
                sound_engine.play_voice_battery()
        elif key == ord('t') or key == ord('T'):
            if presentation_timer_start is None:
                presentation_timer_start = now
            else:
                presentation_timer_start = None
        elif key == ord('s') or key == ord('S'):
            sound_engine.toggle_mute()
        elif key == ord('\t') or key == 9 or key == ord('m') or key == ord('M'):
            is_fullscreen = not is_fullscreen
            if is_fullscreen:
                cv2.setWindowProperty(win_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_FULLSCREEN)
            else:
                cv2.setWindowProperty(win_name, cv2.WND_PROP_FULLSCREEN, cv2.WINDOW_NORMAL)
                cv2.resizeWindow(win_name, 1360, 680)
        elif key == ord(' '):
            if state in ["NORMAL", "COUNTDOWN_5SEC"]:
                sound_engine.play_voice_incapacitated()
                sound_engine.play_announce_stop()
                state = "EVADE_LANE_CHANGE"
                evade_start_time = now
            else:
                state = "NORMAL"
                speed = 82.0
                g_force = 0.0
                current_lane_f = 3.0
                steer_angle = 0.0
                guardrail_dist = 12.8
                sound_engine.reset_announcements()
        elif key == ord('r') or key == ord('R'):
            state = "NORMAL"
            speed = 82.0
            g_force = 0.0
            current_lane_f = 3.0
            steer_angle = 0.0
            guardrail_dist = 12.8
            eyes_closed_timer_start = None
            missing_driver_start = None
            countdown_start_time = 0
            logged_dispatch = False
            logged_sua = False
            logged_battery = False
            sua_start_time = 0
            battery_start_time = 0
            battery_temp = 32.0
            flood_water_level = 0.0
            sound_engine.reset_announcements()

    cap.release()
    cv2.destroyAllWindows()

if __name__ == "__main__":
    main()

