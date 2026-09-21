"""기획전 스케줄 편집기 - Flask + SocketIO 서버"""

import json
import os
import uuid
from datetime import datetime
from pathlib import Path

from flask import Flask, jsonify, render_template, request, send_file, session, redirect, url_for

from flask_socketio import SocketIO, emit

# Supabase 연동
from supabase import create_client, Client

BASE_DIR = Path(__file__).parent
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

app = Flask(__name__)
app.config["SECRET_KEY"] = "schedule-editor-secret-2026"
socketio = SocketIO(app, cors_allowed_origins="*")

# Supabase 설정
SUPABASE_URL = os.environ.get("SUPABASE_URL", "https://kuwpkmwediyalssgzqcx.supabase.co")
SUPABASE_KEY = os.environ.get("SUPABASE_KEY", "sb_publishable_E3gIfkHqq9q5_Q8gUqLCBA_UjdGSMkR")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 접속 중인 사용자 추적
connected_users = {}

# 관리자 패스워드
ADMIN_PASSWORD = "choyy@hsad.co.kr"


# ---- 데이터 파일 읽기/쓰기 (slots만 로컬 JSON 유지) ----

def read_json(filename):
    path = DATA_DIR / filename
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return []


def get_slots():
    return read_json("slots.json")


# ---- Supabase 데이터 함수 ----

def get_campaigns():
    try:
        res = supabase.table("campaigns").select("*").execute()
        campaigns = []
        for row in res.data:
            campaigns.append({
                "id": row["id"],
                "name": row["name"],
                "type": row["type"],
                "category": row["category"],
                "jira": row["jira"],
                "eventNo": row["event_no"],
                "period": {
                    "start": row["period_start"],
                    "end": row["period_end"]
                },
                "memo": row["memo"],
                "color": row["color"]
            })
        return campaigns
    except Exception as e:
        print(f"DB Error (get_campaigns): {e}")
        return []


def save_campaign(campaign):
    try:
        supabase.table("campaigns").upsert({
            "id": campaign["id"],
            "name": campaign.get("name"),
            "type": campaign.get("type"),
            "category": campaign.get("category"),
            "jira": campaign.get("jira"),
            "event_no": campaign.get("eventNo"),
            "period_start": campaign.get("period", {}).get("start"),
            "period_end": campaign.get("period", {}).get("end"),
            "memo": campaign.get("memo"),
            "color": campaign.get("color")
        }).execute()
    except Exception as e:
        print(f"DB Error (save_campaign): {e}")


def delete_campaign_db(campaign_id):
    try:
        supabase.table("campaigns").delete().eq("id", campaign_id).execute()
    except Exception as e:
        print(f"DB Error (delete_campaign): {e}")


def get_schedule():
    try:
        res = supabase.table("schedule").select("*").execute()
        schedule = []
        for row in res.data:
            schedule.append({
                "id": row["id"],
                "campaignId": row["campaign_id"],
                "slotId": row["slot_id"],
                "start": row["start_date"],
                "end": row["end_date"],
                "order": row.get("sort_order", 1),
                "modified": row.get("modified", False),
                "modifiedBy": row.get("modified_by"),
                "modifiedAt": row.get("modified_at"),
                "confirmedBy": row.get("confirmed_by"),
                "confirmedAt": row.get("confirmed_at")
            })
        return schedule
    except Exception as e:
        print(f"DB Error (get_schedule): {e}")
        return []


def save_schedule_item(item):
    try:
        supabase.table("schedule").upsert({
            "id": item["id"],
            "campaign_id": item.get("campaignId"),
            "slot_id": item.get("slotId"),
            "start_date": item.get("start"),
            "end_date": item.get("end"),
            "sort_order": item.get("order", 1),
            "modified": item.get("modified", False),
            "modified_by": item.get("modifiedBy"),
            "modified_at": item.get("modifiedAt"),
            "confirmed_by": item.get("confirmedBy"),
            "confirmed_at": item.get("confirmedAt")
        }).execute()
    except Exception as e:
        print(f"DB Error (save_schedule_item): {e}")


def delete_schedule_item(item_id):
    try:
        supabase.table("schedule").delete().eq("id", item_id).execute()
    except Exception as e:
        print(f"DB Error (delete_schedule_item): {e}")


def get_memos():
    try:
        res = supabase.table("memos").select("*").execute()
        memos = []
        for row in res.data:
            memos.append({
                "id": row["id"],
                "content": row["content"],
                "createdBy": row["created_by"],
                "createdByCode": row["created_by_code"],
                "createdAt": row["created_at"],
                "confirmed": row["confirmed"],
                "confirmedBy": row["confirmed_by"],
                "confirmedAt": row["confirmed_at"]
            })
        return memos
    except Exception as e:
        print(f"DB Error (get_memos): {e}")
        return []


def save_memo(memo):
    try:
        supabase.table("memos").upsert({
            "id": memo["id"],
            "content": memo.get("content"),
            "created_by": memo.get("createdBy"),
            "created_by_code": memo.get("createdByCode"),
            "created_at": memo.get("createdAt"),
            "confirmed": memo.get("confirmed", False),
            "confirmed_by": memo.get("confirmedBy"),
            "confirmed_at": memo.get("confirmedAt")
        }).execute()
    except Exception as e:
        print(f"DB Error (save_memo): {e}")


def delete_memo_db(memo_id):
    try:
        supabase.table("memos").delete().eq("id", memo_id).execute()
    except Exception as e:
        print(f"DB Error (delete_memo): {e}")


# ---- 접근 코드 관리 (Supabase) ----

def get_access_codes():
    try:
        res = supabase.table("access_codes").select("*").execute()
        codes = []
        for row in res.data:
            codes.append({
                "code": row["code"],
                "nickname": row["nickname"],
                "active": True
            })
        return codes
    except Exception as e:
        print(f"DB Error (get_access_codes): {e}")
        return []


def save_access_code(code_data):
    try:
        supabase.table("access_codes").upsert({
            "code": code_data["code"],
            "nickname": code_data.get("nickname")
        }).execute()
    except Exception as e:
        print(f"DB Error (save_access_code): {e}")


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
    return any(c["code"] == code for c in codes)


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

    save_access_code({"code": code, "nickname": nickname})
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

    save_access_code({"code": new_code, "nickname": None})
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
    new_campaign = {
        "id": f"camp_{uuid.uuid4().hex[:8]}",
        "name": data.get("name", ""),
        "type": data.get("type", ""),
        "category": data.get("category", ""),
        "jira": data.get("jira", ""),
        "eventNo": data.get("eventNo", ""),
        "period": data.get("period", {"start": "", "end": ""}),
        "memo": data.get("memo", ""),
    }
    save_campaign(new_campaign)
    campaigns = get_campaigns()
    socketio.emit("campaigns:update", {"campaigns": campaigns})
    return jsonify(new_campaign), 201


@app.route("/api/campaigns/<campaign_id>", methods=["PUT"])
def api_campaigns_update(campaign_id):
    data = request.get_json()
    updated_campaign = {
        "id": campaign_id,
        "name": data.get("name", ""),
        "type": data.get("type", ""),
        "category": data.get("category", ""),
        "jira": data.get("jira", ""),
        "eventNo": data.get("eventNo", ""),
        "period": data.get("period", {"start": "", "end": ""}),
        "memo": data.get("memo", ""),
    }
    save_campaign(updated_campaign)
    campaigns = get_campaigns()
    socketio.emit("campaigns:update", {"campaigns": campaigns})
    return jsonify({"ok": True})


@app.route("/api/campaigns/<campaign_id>", methods=["DELETE"])
def api_campaigns_delete(campaign_id):
    delete_campaign_db(campaign_id)
    campaigns = get_campaigns()
    socketio.emit("campaigns:update", {"campaigns": campaigns})
    return jsonify({"ok": True})


@app.route("/api/schedule", methods=["GET"])
def api_schedule_list():
    return jsonify(get_schedule())


@app.route("/api/schedule", methods=["POST"])
def api_schedule_create():
    data = request.get_json()
    code = session.get("access_code", "unknown")
    slot_id = data.get("slotId")
    new_start = data.get("start")
    new_end = data.get("end")

    # 같은 슬롯에 날짜가 겹치는 스케줄이 있는지 체크
    schedule = get_schedule()
    for s in schedule:
        if s["slotId"] == slot_id:
            existing_start = s.get("start", "")
            existing_end = s.get("end", "")
            # 날짜 겹침 체크: 새 시작 <= 기존 종료 AND 새 종료 >= 기존 시작
            if existing_start and existing_end and new_start and new_end:
                if new_start <= existing_end and new_end >= existing_start:
                    return jsonify({"error": "해당 구좌에 이미 기획전이 배치되어 있습니다."}), 400

    new_item = {
        "id": f"sch_{uuid.uuid4().hex[:8]}",
        "campaignId": data.get("campaignId"),
        "slotId": slot_id,
        "start": new_start,
        "end": new_end,
        "order": data.get("order", 1),
        "modified": True,
        "modifiedBy": code,
        "modifiedAt": datetime.now().isoformat(),
    }
    save_schedule_item(new_item)
    log_access(code, "SCHEDULE_CREATE", f"id={new_item['id']}")
    schedule = get_schedule()
    socketio.emit("schedule:update", {"schedule": schedule})
    return jsonify(new_item), 201


@app.route("/api/schedule/<item_id>", methods=["PUT"])
def api_schedule_update(item_id):
    data = request.get_json()
    code = session.get("access_code", "unknown")

    # 기존 데이터 가져오기
    existing = None
    for s in get_schedule():
        if s["id"] == item_id:
            existing = s
            break

    if not existing:
        return jsonify({"error": "스케줄을 찾을 수 없습니다."}), 404

    # 기존 데이터에 새 데이터 병합
    updated_item = {
        "id": item_id,
        "campaignId": data.get("campaignId") or existing.get("campaignId"),
        "slotId": data.get("slotId") or existing.get("slotId"),
        "start": data.get("start") or existing.get("start"),
        "end": data.get("end") or existing.get("end"),
        "order": data.get("order") or existing.get("order", 1),
        "modified": True,
        "modifiedBy": code,
        "modifiedAt": datetime.now().isoformat(),
    }
    save_schedule_item(updated_item)
    log_access(code, "SCHEDULE_UPDATE", f"id={item_id}")
    schedule = get_schedule()
    socketio.emit("schedule:update", {"schedule": schedule})
    return jsonify({"ok": True})


@app.route("/api/schedule/<item_id>", methods=["DELETE"])
def api_schedule_delete(item_id):
    code = session.get("access_code", "unknown")
    delete_schedule_item(item_id)
    log_access(code, "SCHEDULE_DELETE", f"id={item_id}")
    schedule = get_schedule()
    socketio.emit("schedule:update", {"schedule": schedule})
    return jsonify({"ok": True})


@app.route("/api/schedule/<item_id>/confirm", methods=["POST"])
def api_schedule_confirm(item_id):
    """수정 확인 - modified 플래그 해제"""
    code = session.get("access_code", "unknown")
    schedule = get_schedule()
    for s in schedule:
        if s["id"] == item_id:
            s["modified"] = False
            s["confirmedBy"] = code
            s["confirmedAt"] = datetime.now().isoformat()
            save_schedule_item(s)
            break
    log_access(code, "SCHEDULE_CONFIRM", f"id={item_id}")
    schedule = get_schedule()
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
    save_memo(memo)
    log_access(code, "MEMO_CREATE", f"id={memo['id']}")
    memos = get_memos()
    socketio.emit("memos:update", {"memos": memos})
    return jsonify(memo), 201


@app.route("/api/memos/<memo_id>", methods=["PUT"])
def api_memos_update(memo_id):
    """메모 수정"""
    data = request.json
    code = session.get("access_code", "unknown")
    display_name = get_display_name(code)
    updated_memo = {
        "id": memo_id,
        "content": data.get("content", ""),
        "createdByCode": code,
        "createdBy": display_name,
        "createdAt": datetime.now().isoformat(),
        "confirmed": False,
        "confirmedBy": None,
        "confirmedAt": None,
    }
    save_memo(updated_memo)
    log_access(code, "MEMO_UPDATE", f"id={memo_id}")
    memos = get_memos()
    socketio.emit("memos:update", {"memos": memos})
    return jsonify({"ok": True})


@app.route("/api/memos/<memo_id>", methods=["DELETE"])
def api_memos_delete(memo_id):
    """메모 삭제"""
    code = session.get("access_code", "unknown")
    delete_memo_db(memo_id)
    log_access(code, "MEMO_DELETE", f"id={memo_id}")
    memos = get_memos()
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
            save_memo(m)
            break
    log_access(code, "MEMO_CONFIRM", f"id={memo_id}")
    memos = get_memos()
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
    """미리보기한 기획전들을 실제로 저장 (중복 체크)"""
    data = request.get_json()
    new_campaigns = data.get("campaigns", [])
    existing = get_campaigns()

    # 기존 기획전 키 세트 (이름 + 시작일 + 종료일)
    existing_keys = set()
    for c in existing:
        key = (c.get("name", ""), c.get("period", {}).get("start", ""), c.get("period", {}).get("end", ""))
        existing_keys.add(key)

    added = 0
    skipped = 0
    for c in new_campaigns:
        key = (c.get("name", ""), c.get("period", {}).get("start", ""), c.get("period", {}).get("end", ""))
        if key in existing_keys:
            skipped += 1
            continue
        c["id"] = f"camp_{uuid.uuid4().hex[:8]}"
        save_campaign(c)
        existing_keys.add(key)
        added += 1

    campaigns = get_campaigns()
    socketio.emit("campaigns:update", {"campaigns": campaigns})
    return jsonify({"added": added, "skipped": skipped})


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
    port = int(os.environ.get("PORT", 5050))
    debug = os.environ.get("RENDER") is None
    print(f"서버 시작: http://localhost:{port}")
    socketio.run(app, host="0.0.0.0", port=port, debug=debug, allow_unsafe_werkzeug=True)
