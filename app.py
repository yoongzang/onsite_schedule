"""기획전 스케줄 편집기 - Flask + SocketIO 서버"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, session, redirect, url_for

from flask_socketio import SocketIO, emit

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

app = Flask(__name__)
app.config["SECRET_KEY"] = "schedule-editor-secret-2026"
socketio = SocketIO(app, cors_allowed_origins="*")

# 접속 중인 사용자 추적
connected_users = {}

# 관리자 패스워드
ADMIN_PASSWORD = "choyy@hsad.co.kr"


# ---- 데이터 파일 읽기/쓰기 ----

def read_json(filename):
    path = DATA_DIR / filename
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def write_json(filename, data):
    path = DATA_DIR / filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")


def get_campaigns():
    return read_json("campaigns.json")


def get_slots():
    return read_json("slots.json")


def get_schedule():
    return read_json("schedule.json")


def save_campaigns(data):
    write_json("campaigns.json", data)


def save_schedule(data):
    write_json("schedule.json", data)


def get_memos():
    return read_json("memos.json")


def save_memos(data):
    write_json("memos.json", data)


# ---- 접근 코드 관리 ----

def get_access_codes():
    return read_json("access_codes.json")


def save_access_codes(data):
    write_json("access_codes.json", data)


def generate_next_code(prefix="HSAD"):
    """HSAD001~999 또는 LG001~999 순차 발급"""
    codes = get_access_codes()
    if not codes:
        next_num = 1
    else:
        nums = [int(c["code"].replace(prefix, "")) for c in codes if c["code"].startswith(prefix)]
        next_num = max(nums) + 1 if nums else 1

    if next_num > 999:
        return None  # 코드 소진

    return f"{prefix}{next_num:03d}"


def is_valid_code(code):
    """발급된 코드인지 확인"""
    codes = get_access_codes()
    return any(c["code"] == code and c["active"] for c in codes)


def log_access(code, action, details=""):
    """접근 로그 기록"""
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    log_path = LOG_DIR / "access.log"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    log_entry = f"[{timestamp}] [{code}] {action} {details}\n"
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(log_entry)


# ---- 페이지 라우트 ----

@app.route("/")
def index():
    """호스트 페이지 (로그인)"""
    return render_template("login.html")


@app.route("/app")
def app_page():
    """메인 앱 페이지 (접근 코드 필요)"""
    code = session.get("access_code")
    if not code or not is_valid_code(code):
        return redirect(url_for("index"))
    # 닉네임 없으면 닉네임 설정으로
    code_info = get_code_info(code)
    if not code_info or not code_info.get("nickname"):
        return redirect(url_for("nickname_page"))
    return render_template("index.html")


@app.route("/nickname")
def nickname_page():
    """닉네임 설정 페이지"""
    code = session.get("access_code")
    if not code or not is_valid_code(code):
        return redirect(url_for("index"))
    return render_template("nickname.html")


@app.route("/api/auth/nickname", methods=["POST"])
def api_set_nickname():
    """닉네임 설정"""
    code = session.get("access_code")
    if not code:
        return jsonify({"ok": False, "error": "로그인이 필요합니다."}), 401

    data = request.get_json()
    nickname = data.get("nickname", "").strip()

    if not nickname or len(nickname) > 5:
        return jsonify({"ok": False, "error": "닉네임은 1~5자로 입력해주세요."}), 400

    codes = get_access_codes()
    for c in codes:
        if c["code"] == code:
            c["nickname"] = nickname
            break
    save_access_codes(codes)
    log_access(code, "NICKNAME_SET", nickname)

    return jsonify({"ok": True, "redirect": "/app"})


def get_display_name(code):
    """코드+닉네임 형태로 표시명 반환"""
    code_info = get_code_info(code)
    if code_info and code_info.get("nickname"):
        return f"{code}({code_info['nickname']})"
    return code


# ---- 접근 코드 API ----

def get_code_info(code):
    """코드 정보 가져오기"""
    codes = get_access_codes()
    for c in codes:
        if c["code"] == code:
            return c
    return None


@app.route("/api/auth/login", methods=["POST"])
def api_auth_login():
    """접근 코드로 로그인"""
    data = request.get_json()
    code = data.get("code", "").strip().upper()

    if not is_valid_code(code):
        log_access(code, "LOGIN_FAILED", "Invalid code")
        return jsonify({"ok": False, "error": "유효하지 않은 접근 코드입니다."}), 401

    session["access_code"] = code
    code_info = get_code_info(code)

    # 닉네임이 없으면 닉네임 설정 페이지로
    if not code_info or not code_info.get("nickname"):
        log_access(code, "LOGIN_SUCCESS", "needs nickname")
        return jsonify({"ok": True, "redirect": "/nickname"})

    log_access(code, "LOGIN_SUCCESS")
    return jsonify({"ok": True, "redirect": "/app"})


@app.route("/api/auth/issue", methods=["POST"])
def api_auth_issue():
    """접근 코드 발급 (관리자 패스워드 필요)"""
    data = request.get_json()
    password = data.get("password", "")
    prefix = data.get("prefix", "HSAD")

    if prefix not in ["HSAD", "LG"]:
        prefix = "HSAD"

    if password != ADMIN_PASSWORD:
        log_access("ADMIN", "ISSUE_FAILED", "Wrong password")
        return jsonify({"ok": False, "error": "패스워드가 일치하지 않습니다."}), 401

    new_code = generate_next_code(prefix)
    if not new_code:
        return jsonify({"ok": False, "error": f"발급 가능한 {prefix} 코드가 없습니다. (최대 999개)"}), 400

    codes = get_access_codes()
    codes.append({
        "code": new_code,
        "active": True,
        "nickname": None,
        "issuedAt": datetime.now().isoformat(),
    })
    save_access_codes(codes)
    log_access(new_code, "ISSUED", f"by admin ({prefix})")

    return jsonify({"ok": True, "code": new_code})


@app.route("/api/auth/logout", methods=["POST"])
def api_auth_logout():
    """로그아웃"""
    code = session.get("access_code", "unknown")
    session.pop("access_code", None)
    log_access(code, "LOGOUT")
    return jsonify({"ok": True})


# ---- REST API ----

@app.route("/api/slots")
def api_slots():
    return jsonify(get_slots())


@app.route("/api/campaigns", methods=["GET"])
def api_campaigns_list():
    return jsonify(get_campaigns())


@app.route("/api/campaigns", methods=["POST"])
def api_campaigns_create():
    data = request.get_json()
    campaigns = get_campaigns()
    new_campaign = {
        "id": f"camp_{uuid.uuid4().hex[:8]}",
        "name": data.get("name", ""),
        "type": data.get("type", ""),
        "category": data.get("category", ""),
        "jira": data.get("jira", ""),
        "period": data.get("period", {"start": "", "end": ""}),
        "memo": data.get("memo", ""),
    }
    campaigns.append(new_campaign)
    save_campaigns(campaigns)
    socketio.emit("campaigns:update", {"campaigns": campaigns})
    return jsonify(new_campaign), 201


@app.route("/api/campaigns/<campaign_id>", methods=["PUT"])
def api_campaigns_update(campaign_id):
    data = request.get_json()
    campaigns = get_campaigns()
    for c in campaigns:
        if c["id"] == campaign_id:
            c.update({k: v for k, v in data.items() if k != "id"})
            break
    save_campaigns(campaigns)
    socketio.emit("campaigns:update", {"campaigns": campaigns})
    return jsonify({"ok": True})


@app.route("/api/campaigns/<campaign_id>", methods=["DELETE"])
def api_campaigns_delete(campaign_id):
    campaigns = [c for c in get_campaigns() if c["id"] != campaign_id]
    save_campaigns(campaigns)
    socketio.emit("campaigns:update", {"campaigns": campaigns})
    return jsonify({"ok": True})


@app.route("/api/schedule", methods=["GET"])
def api_schedule_list():
    return jsonify(get_schedule())


@app.route("/api/schedule", methods=["POST"])
def api_schedule_create():
    data = request.get_json()
    schedule = get_schedule()
    code = session.get("access_code", "unknown")
    new_item = {
        "id": f"sch_{uuid.uuid4().hex[:8]}",
        "campaignId": data.get("campaignId"),
        "slotId": data.get("slotId"),
        "start": data.get("start"),
        "end": data.get("end"),
        "order": data.get("order", 1),
        "modified": True,  # 새로 추가된 항목은 수정됨 표시
        "modifiedBy": code,
        "modifiedAt": datetime.now().isoformat(),
    }
    schedule.append(new_item)
    save_schedule(schedule)
    log_access(code, "SCHEDULE_CREATE", f"id={new_item['id']}")
    socketio.emit("schedule:update", {"schedule": schedule})
    return jsonify(new_item), 201


@app.route("/api/schedule/<item_id>", methods=["PUT"])
def api_schedule_update(item_id):
    data = request.get_json()
    schedule = get_schedule()
    code = session.get("access_code", "unknown")
    for s in schedule:
        if s["id"] == item_id:
            s.update({k: v for k, v in data.items() if k != "id"})
            # modified 플래그를 명시적으로 false로 보내지 않는 한 true로 설정
            if "modified" not in data:
                s["modified"] = True
                s["modifiedBy"] = code
                s["modifiedAt"] = datetime.now().isoformat()
            break
    save_schedule(schedule)
    log_access(code, "SCHEDULE_UPDATE", f"id={item_id}")
    socketio.emit("schedule:update", {"schedule": schedule})
    return jsonify({"ok": True})


@app.route("/api/schedule/<item_id>", methods=["DELETE"])
def api_schedule_delete(item_id):
    code = session.get("access_code", "unknown")
    schedule = [s for s in get_schedule() if s["id"] != item_id]
    save_schedule(schedule)
    log_access(code, "SCHEDULE_DELETE", f"id={item_id}")
    socketio.emit("schedule:update", {"schedule": schedule})
    return jsonify({"ok": True})


@app.route("/api/schedule/<item_id>/confirm", methods=["POST"])
def api_schedule_confirm(item_id):
    """수정 확인 - modified 플래그 제거"""
    schedule = get_schedule()
    code = session.get("access_code", "unknown")
    for s in schedule:
        if s["id"] == item_id:
            s["modified"] = False
            s["confirmedBy"] = code
            s["confirmedAt"] = datetime.now().isoformat()
            break
    save_schedule(schedule)
    log_access(code, "SCHEDULE_CONFIRM", f"id={item_id}")
    socketio.emit("schedule:update", {"schedule": schedule})
    return jsonify({"ok": True})


# ---- 메모 API ----

@app.route("/api/memos", methods=["GET"])
def api_memos_list():
    return jsonify(get_memos())


@app.route("/api/memos", methods=["POST"])
def api_memos_create():
    """메모 생성 (최대 3개)"""
    memos = get_memos()
    if len(memos) >= 3:
        return jsonify({"error": "메모는 최대 3개까지만 가능합니다."}), 400

    data = request.json
    code = session.get("access_code", "unknown")
    display_name = get_display_name(code)
    memo = {
        "id": f"memo_{uuid.uuid4().hex[:8]}",
        "content": data.get("content", ""),
        "createdByCode": code,
        "createdBy": display_name,
        "createdAt": datetime.now().isoformat(),
        "confirmed": False,
        "confirmedBy": None,
        "confirmedAt": None,
    }
    memos.append(memo)
    save_memos(memos)
    log_access(code, "MEMO_CREATE", f"id={memo['id']}")
    socketio.emit("memos:update", {"memos": memos})
    return jsonify(memo), 201


@app.route("/api/memos/<memo_id>", methods=["PUT"])
def api_memos_update(memo_id):
    """메모 수정"""
    memos = get_memos()
    data = request.json
    code = session.get("access_code", "unknown")
    display_name = get_display_name(code)
    for m in memos:
        if m["id"] == memo_id:
            m["content"] = data.get("content", m["content"])
            m["createdByCode"] = code
            m["createdBy"] = display_name
            m["createdAt"] = datetime.now().isoformat()
            m["confirmed"] = False
            m["confirmedBy"] = None
            m["confirmedAt"] = None
            break
    save_memos(memos)
    log_access(code, "MEMO_UPDATE", f"id={memo_id}")
    socketio.emit("memos:update", {"memos": memos})
    return jsonify({"ok": True})


@app.route("/api/memos/<memo_id>", methods=["DELETE"])
def api_memos_delete(memo_id):
    """메모 삭제"""
    memos = get_memos()
    code = session.get("access_code", "unknown")
    memos = [m for m in memos if m["id"] != memo_id]
    save_memos(memos)
    log_access(code, "MEMO_DELETE", f"id={memo_id}")
    socketio.emit("memos:update", {"memos": memos})
    return jsonify({"ok": True})


@app.route("/api/memos/<memo_id>/confirm", methods=["POST"])
def api_memos_confirm(memo_id):
    """메모 확인완료"""
    memos = get_memos()
    code = session.get("access_code", "unknown")
    display_name = get_display_name(code)
    for m in memos:
        if m["id"] == memo_id:
            if m.get("createdByCode") == code:
                return jsonify({"error": "본인이 작성한 메모는 본인이 확인할 수 없습니다."}), 400
            m["confirmed"] = True
            m["confirmedBy"] = display_name
            m["confirmedAt"] = datetime.now().isoformat()
            break
    save_memos(memos)
    log_access(code, "MEMO_CONFIRM", f"id={memo_id}")
    socketio.emit("memos:update", {"memos": memos})
    return jsonify({"ok": True})


# ---- 엑셀 업로드/다운로드 ----

@app.route("/api/upload/preview", methods=["POST"])
def api_upload_preview():
    """엑셀 파일을 파싱해서 미리보기 데이터 반환"""
    if "file" not in request.files:
        return jsonify({"error": "파일이 없습니다."}), 400

    file = request.files["file"]
    if not file.filename.endswith((".xlsx", ".xls")):
        return jsonify({"error": "엑셀 파일만 지원합니다."}), 400

    try:
        import openpyxl
        from io import BytesIO

        wb = openpyxl.load_workbook(BytesIO(file.read()), data_only=True)
        ws = wb.active

        headers = [cell.value for cell in ws[1]]
        campaigns = []

        for row in ws.iter_rows(min_row=2, values_only=True):
            if not any(row):
                continue

            row_dict = dict(zip(headers, row))
            campaign = {
                "name": str(row_dict.get("기획전명", "") or ""),
                "type": str(row_dict.get("유형", "") or ""),
                "category": str(row_dict.get("구분", "") or ""),
                "jira": str(row_dict.get("JIRA", "") or "").replace("ONMKT-", ""),
                "eventNo": str(row_dict.get("기획전번호", "") or ""),
                "period": {
                    "start": _parse_date(row_dict.get("시작일")),
                    "end": _parse_date(row_dict.get("종료일")),
                },
                "memo": str(row_dict.get("참고사항", "") or "")[:200],
            }
            if campaign["name"]:
                campaigns.append(campaign)

        return jsonify({"campaigns": campaigns})
    except Exception as e:
        return jsonify({"error": f"파일 처리 오류: {str(e)}"}), 400


def _parse_date(val):
    """다양한 날짜 형식을 YYYY-MM-DD로 변환"""
    if not val:
        return ""
    if isinstance(val, datetime):
        return val.strftime("%Y-%m-%d")
    try:
        from datetime import datetime as dt
        for fmt in ["%Y-%m-%d", "%Y.%m.%d", "%Y/%m/%d", "%m/%d/%Y"]:
            try:
                return dt.strptime(str(val), fmt).strftime("%Y-%m-%d")
            except ValueError:
                continue
        return str(val)
    except Exception:
        return str(val)


@app.route("/api/upload/confirm", methods=["POST"])
def api_upload_confirm():
    """미리보기한 기획전들을 실제로 저장"""
    data = request.get_json()
    new_campaigns = data.get("campaigns", [])
    campaigns = get_campaigns()

    added = 0
    for c in new_campaigns:
        c["id"] = f"camp_{uuid.uuid4().hex[:8]}"
        campaigns.append(c)
        added += 1

    save_campaigns(campaigns)
    socketio.emit("campaigns:update", {"campaigns": campaigns})
    return jsonify({"added": added})


@app.route("/api/template")
def api_template():
    """엑셀 템플릿 다운로드"""
    try:
        import openpyxl
        from io import BytesIO

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = "기획전 목록"

        headers = ["기획전명", "유형", "구분", "JIRA", "기획전번호", "시작일", "종료일", "참고사항"]
        ws.append(headers)

        widths = [30, 12, 10, 15, 20, 12, 12, 40]
        for i, w in enumerate(widths, 1):
            ws.column_dimensions[openpyxl.utils.get_column_letter(i)].width = w

        ws.append(["(예시) 가을 가전 대전", "통합", "신규", "1530", "12345", "2026-09-15", "2026-09-30", "메모 입력"])

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        today = datetime.now().strftime("%y%m%d")
        return send_file(
            buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"온사이트배너_기획전 등록 양식_{today}.xlsx"
        )
    except ImportError:
        return jsonify({"error": "openpyxl이 설치되지 않았습니다."}), 500


@app.route("/api/export")
def api_export():
    """현재 스케줄을 캘린더 형태 엑셀로 다운로드"""
    try:
        import openpyxl
        from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
        from openpyxl.utils import get_column_letter
        from io import BytesIO
        import calendar

        year = int(request.args.get("year", datetime.now().year))
        month = int(request.args.get("month", datetime.now().month))
        area_filter = request.args.get("area", "홈메인")

        schedule = get_schedule()
        campaigns = get_campaigns()
        slots = get_slots()

        camp_dict = {c["id"]: c for c in campaigns}
        slot_dict = {s["id"]: s for s in slots}

        # 해당 영역 슬롯만 필터링
        area_slots = [s for s in slots if s.get("area") == area_filter]

        # 그룹별로 슬롯 정리
        groups = {}
        for s in area_slots:
            g = s.get("group", "기타")
            if g not in groups:
                groups[g] = []
            groups[g].append(s)

        # 월의 주차 계산 (일~토 기준)
        cal = calendar.Calendar(firstweekday=6)  # 일요일 시작
        weeks = list(cal.monthdatescalendar(year, month))

        wb = openpyxl.Workbook()
        ws = wb.active
        ws.title = f"{year}년 {month}월"

        # 스타일 정의
        thin_border = Border(
            left=Side(style='thin'),
            right=Side(style='thin'),
            top=Side(style='thin'),
            bottom=Side(style='thin')
        )
        header_fill = PatternFill(start_color="E0E0E0", end_color="E0E0E0", fill_type="solid")
        weekend_fill = PatternFill(start_color="FFF0F0", end_color="FFF0F0", fill_type="solid")
        today_fill = PatternFill(start_color="FFFFE0", end_color="FFFFE0", fill_type="solid")

        # 유형별 색상
        type_colors = {
            "통합": "E3F272",
            "전략런칭": "D6D9D2",
            "일반": "E9E9E9",
            "구독": "DBFFEB",
            "라이브": "D9E0A4",
        }
        light_text_types = ["임직원", "제휴", "이벤트", "기타"]

        row = 1

        # 제목
        ws.cell(row=row, column=1, value=f"{year}년 {month}월 {area_filter} 스케줄")
        ws.cell(row=row, column=1).font = Font(bold=True, size=14)
        row += 2

        # 각 주차별로 테이블 생성
        for week_idx, week in enumerate(weeks):
            # 주차 범위 표시
            week_start = week[0]
            week_end = week[6]
            ws.cell(row=row, column=1, value=f"{week_idx+1}주차 ({week_start.month}/{week_start.day} ~ {week_end.month}/{week_end.day})")
            ws.cell(row=row, column=1).font = Font(bold=True)
            row += 1

            # 헤더: 구분 + 일~토
            ws.cell(row=row, column=1, value="구분")
            ws.cell(row=row, column=1).fill = header_fill
            ws.cell(row=row, column=1).border = thin_border
            ws.cell(row=row, column=1).alignment = Alignment(horizontal='center')

            weekday_names = ["일", "월", "화", "수", "목", "금", "토"]
            for col, (day, wd_name) in enumerate(zip(week, weekday_names), 2):
                cell = ws.cell(row=row, column=col, value=f"{wd_name}\n{day.day}")
                cell.fill = header_fill
                cell.border = thin_border
                cell.alignment = Alignment(horizontal='center', wrap_text=True)
                if wd_name in ["일", "토"]:
                    cell.font = Font(color="FF0000")

            row += 1

            # 그룹별 슬롯 행
            for group_name, group_slots in groups.items():
                # 그룹 헤더
                ws.cell(row=row, column=1, value=group_name)
                ws.cell(row=row, column=1).font = Font(bold=True)
                ws.merge_cells(start_row=row, start_column=1, end_row=row, end_column=8)
                row += 1

                # 슬롯별 행
                for slot in sorted(group_slots, key=lambda x: (x.get("order") or 0, x.get("category") or "")):
                    slot_label = slot.get("category") or slot.get("order") or ""
                    ws.cell(row=row, column=1, value=slot_label)
                    ws.cell(row=row, column=1).border = thin_border
                    ws.cell(row=row, column=1).alignment = Alignment(horizontal='center')

                    for col, day in enumerate(week, 2):
                        date_str = day.strftime("%Y-%m-%d")
                        cell = ws.cell(row=row, column=col)
                        cell.border = thin_border
                        cell.alignment = Alignment(horizontal='center', vertical='center', wrap_text=True)

                        # 주말 배경
                        if col == 2 or col == 8:  # 일, 토
                            cell.fill = weekend_fill

                        # 오늘 배경
                        if day == datetime.now().date():
                            cell.fill = today_fill

                        # 해당 날짜에 스케줄 찾기
                        for sch in schedule:
                            if sch.get("slotId") != slot.get("id"):
                                continue
                            sch_start = sch.get("start", "")
                            sch_end = sch.get("end", "")
                            if sch_start <= date_str <= sch_end:
                                camp = camp_dict.get(sch.get("campaignId"), {})
                                camp_name = camp.get("name", "")
                                camp_type = camp.get("type", "")

                                cell.value = camp_name

                                # 배경색
                                bg_color = type_colors.get(camp_type, "949494")
                                cell.fill = PatternFill(start_color=bg_color, end_color=bg_color, fill_type="solid")

                                # 텍스트 색상
                                if camp_type in light_text_types:
                                    cell.font = Font(color="FFFFFF", size=9)
                                else:
                                    cell.font = Font(size=9)
                                break

                    row += 1

            row += 1  # 그룹 간 간격

        # 컬럼 너비 설정
        ws.column_dimensions['A'].width = 8
        for col in range(2, 9):
            ws.column_dimensions[get_column_letter(col)].width = 15

        buffer = BytesIO()
        wb.save(buffer)
        buffer.seek(0)

        today = datetime.now().strftime("%Y%m%d")
        return send_file(
            buffer,
            mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            as_attachment=True,
            download_name=f"스케줄_{area_filter}_{year}{month:02d}_{today}.xlsx"
        )
    except ImportError:
        return jsonify({"error": "openpyxl이 설치되지 않았습니다."}), 500


# ---- WebSocket 이벤트 ----

@socketio.on("connect")
def handle_connect():
    sid = request.sid
    connected_users[sid] = {
        "id": sid,
        "name": f"User_{sid[:6]}",
        "joinedAt": datetime.now().isoformat(),
    }
    emit("users:list", {"users": list(connected_users.values())}, broadcast=True)


@socketio.on("disconnect")
def handle_disconnect():
    sid = request.sid
    if sid in connected_users:
        del connected_users[sid]
    emit("users:list", {"users": list(connected_users.values())}, broadcast=True)


@socketio.on("user:setName")
def handle_set_name(data):
    sid = request.sid
    if sid in connected_users:
        connected_users[sid]["name"] = data.get("name", connected_users[sid]["name"])
    emit("users:list", {"users": list(connected_users.values())}, broadcast=True)


if __name__ == "__main__":
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    print(f"서버 시작: http://localhost:5050")
    socketio.run(app, host="0.0.0.0", port=5050, debug=True, allow_unsafe_werkzeug=True)
