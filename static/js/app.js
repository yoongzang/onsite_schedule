/* 온사이트 배너 스케줄 관리 - 메인 JavaScript */

// 모바일 사이드바 토글
function toggleSidebar() {
  const sidebar = document.getElementById('campaignPanel');
  const overlay = document.getElementById('sidebarOverlay');
  sidebar.classList.toggle('open');
  overlay.classList.toggle('open');
}

// 상태 관리
const state = {
  campaigns: [],
  slots: [],
  schedule: [],
  memos: [],
  users: [],
  currentArea: '홈메인',
  currentYear: new Date().getFullYear(),
  currentMonth: new Date().getMonth(),
  editingCampaign: null,
};

// 유형별 색상 매핑
const TYPE_COLORS = {
  '통합': '#E3F272',
  '전략런칭': '#D6D9D2',
  '일반': '#E9E9E9',
  '구독': '#DBFFEB',
  '임직원': '#949494',
  '제휴': '#949494',
  '라이브': '#D9E0A4',
  '이벤트': '#949494',
  '홈스타일': '#DBFFEB',
  '베스트샵': '#949494',
  '기타': '#949494',
};

// 텍스트가 흰색이어야 하는 유형 (어두운 배경색)
const LIGHT_TEXT_TYPES = ['임직원', '제휴', '이벤트', '베스트샵', '기타'];

function getTextColor(type) {
  if (LIGHT_TEXT_TYPES.includes(type)) return '#FFFFFF';
  return '#333333';
}

function getEventUrl(eventNo) {
  if (!eventNo) return '';
  if (eventNo.startsWith('PE')) {
    return `https://www.lge.co.kr/benefits/exhibitions/detail-${eventNo}`;
  }
  return eventNo;
}

// 날짜 유틸
const DAY_MS = 86400000;
const WEEKDAYS = ['일', '월', '화', '수', '목', '금', '토'];

// 2026년 공휴일 (고정 공휴일 + 대체공휴일)
const HOLIDAYS_2026 = [
  '2026-01-01', // 신정
  '2026-02-16', '2026-02-17', '2026-02-18', // 설날
  '2026-03-01', // 삼일절
  '2026-05-05', // 어린이날
  '2026-05-24', // 부처님오신날
  '2026-06-06', // 현충일
  '2026-08-15', // 광복절
  '2026-09-24', '2026-09-25', '2026-09-26', // 추석
  '2026-10-03', // 개천절
  '2026-10-09', // 한글날
  '2026-12-25', // 성탄절
];

function isHoliday(dateStr) {
  return HOLIDAYS_2026.includes(dateStr);
}

function formatDateISO(d) {
  const date = new Date(d);
  const y = date.getFullYear();
  const m = String(date.getMonth() + 1).padStart(2, '0');
  const day = String(date.getDate()).padStart(2, '0');
  return `${y}-${m}-${day}`;
}

function getMonday(d) {
  const date = new Date(d);
  const day = date.getDay();
  const diff = date.getDate() - day + (day === 0 ? -6 : 1);
  return new Date(date.setDate(diff));
}

function addDays(d, n) {
  return new Date(d.getTime() + n * DAY_MS);
}

function isToday(d) {
  const today = new Date();
  return d.getFullYear() === today.getFullYear() &&
         d.getMonth() === today.getMonth() &&
         d.getDate() === today.getDate();
}

function isWeekend(d) {
  const day = d.getDay();
  return day === 0 || day === 6;
}

// 초기화
function init() {
  initSocket();
  initEventListeners();
  loadData();
  updateMonthDisplay();
}

function updateMonthDisplay() {
  document.getElementById('currentMonth').textContent =
    `${state.currentYear}년 ${state.currentMonth + 1}월`;
}

// Socket.IO 초기화
let socket;

function initSocket() {
  socket = io();

  socket.on('connect', () => {
    console.log('Socket 연결됨');
  });

  socket.on('users:list', (data) => {
    state.users = data.users;
    renderUsersOnline();
  });

  socket.on('campaigns:update', (data) => {
    state.campaigns = data.campaigns;
    renderCampaigns();
    renderCalendar();
  });

  socket.on('schedule:update', (data) => {
    state.schedule = data.schedule;
    renderCalendar();
  });

  socket.on('memos:update', (data) => {
    state.memos = data.memos;
    updateMemoButton();
    renderMemos();
  });
}

// 데이터 로드
async function loadData() {
  try {
    const [slotsRes, campaignsRes, scheduleRes, memosRes] = await Promise.all([
      fetch('/api/slots'),
      fetch('/api/campaigns'),
      fetch('/api/schedule'),
      fetch('/api/memos'),
    ]);

    state.slots = await slotsRes.json();
    state.campaigns = await campaignsRes.json();
    state.schedule = await scheduleRes.json();
    state.memos = await memosRes.json();

    renderCampaigns();
    renderCalendar();
    updateMemoButton();
  } catch (e) {
    console.error('데이터 로드 실패:', e);
  }
}

// 저장 버튼 - 서버 데이터 동기화
async function saveAllData() {
  const btn = document.getElementById('saveBtn');
  const originalText = btn.innerHTML;
  btn.innerHTML = '⏳ 저장 중...';
  btn.disabled = true;

  try {
    await loadData();
    btn.innerHTML = '✅ 저장 완료!';
    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }, 1500);
  } catch (e) {
    btn.innerHTML = '❌ 실패';
    setTimeout(() => {
      btn.innerHTML = originalText;
      btn.disabled = false;
    }, 1500);
  }
}

// 이벤트 리스너
function initEventListeners() {
  // 테마 토글
  document.getElementById('themeToggle').addEventListener('click', () => {
    document.body.classList.toggle('dark');
  });

  // 영역 탭
  document.querySelectorAll('.area-tab').forEach(tab => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.area-tab').forEach(t => t.classList.remove('active'));
      tab.classList.add('active');
      state.currentArea = tab.dataset.area;
      renderCalendar();
    });
  });

  // 월 네비게이션
  document.getElementById('prevMonthBtn').addEventListener('click', () => {
    state.currentMonth--;
    if (state.currentMonth < 0) {
      state.currentMonth = 11;
      state.currentYear--;
    }
    updateMonthDisplay();
    renderCalendar();
  });

  document.getElementById('nextMonthBtn').addEventListener('click', () => {
    state.currentMonth++;
    if (state.currentMonth > 11) {
      state.currentMonth = 0;
      state.currentYear++;
    }
    updateMonthDisplay();
    renderCalendar();
  });

  document.getElementById('todayBtn').addEventListener('click', () => {
    const today = new Date();
    state.currentYear = today.getFullYear();
    state.currentMonth = today.getMonth();
    updateMonthDisplay();
    renderCalendar();
  });

  // 기획전 추가 버튼
  document.getElementById('addCampaignBtn').addEventListener('click', () => {
    openCampaignModal();
  });

  // 엑셀 업로드 버튼
  document.getElementById('uploadExcelBtn').addEventListener('click', () => {
    openExcelModal();
  });

  // 엑셀 다운로드 버튼
  document.getElementById('exportBtn').addEventListener('click', () => {
    exportScheduleToExcel();
  });

  // 메모 버튼
  document.getElementById('memoBtn').addEventListener('click', () => {
    openMemoModal();
  });

  // 기획전 검색
  document.getElementById('campaignSearch').addEventListener('input', (e) => {
    renderCampaigns(e.target.value);
  });

  // 모달 닫기
  document.getElementById('modalClose').addEventListener('click', closeCampaignModal);
  document.getElementById('modalCancel').addEventListener('click', closeCampaignModal);
  document.getElementById('campaignModal').addEventListener('click', (e) => {
    if (e.target.id === 'campaignModal') closeCampaignModal();
  });

  // 기획전 폼 제출
  document.getElementById('campaignForm').addEventListener('submit', async (e) => {
    e.preventDefault();
    await saveCampaign();
  });

  // 기획전번호 입력 시 URL 링크 표시
  document.getElementById('campEventNo').addEventListener('input', (e) => {
    const val = e.target.value.trim();
    const linkEl = document.getElementById('eventLink');
    const anchorEl = document.getElementById('eventLinkAnchor');
    if (val) {
      const fullUrl = getEventUrl(val);
      linkEl.style.display = 'block';
      anchorEl.href = fullUrl;
      anchorEl.textContent = fullUrl;
    } else {
      linkEl.style.display = 'none';
    }
  });

  // 참고사항 글자수 카운트
  document.getElementById('campMemo').addEventListener('input', (e) => {
    document.getElementById('memoCount').textContent = e.target.value.length;
  });

  // 엑셀 업로드 영역
  const uploadArea = document.getElementById('uploadArea');
  const excelFile = document.getElementById('excelFile');

  uploadArea.addEventListener('click', () => excelFile.click());
  uploadArea.addEventListener('dragover', (e) => {
    e.preventDefault();
    uploadArea.classList.add('dragover');
  });
  uploadArea.addEventListener('dragleave', () => {
    uploadArea.classList.remove('dragover');
  });
  uploadArea.addEventListener('drop', (e) => {
    e.preventDefault();
    uploadArea.classList.remove('dragover');
    if (e.dataTransfer.files.length) {
      handleExcelFile(e.dataTransfer.files[0]);
    }
  });
  excelFile.addEventListener('change', (e) => {
    if (e.target.files.length) {
      handleExcelFile(e.target.files[0]);
    }
  });
}

// 접속자 표시
function renderUsersOnline() {
  const el = document.getElementById('usersOnline');
  el.querySelector('.users-count').textContent = `${state.users.length}명 접속 중`;
}

// 기획전 목록 렌더링
function renderCampaigns(searchTerm = '') {
  const list = document.getElementById('campaignList');
  const today = formatDateISO(new Date());
  const monthEnd = getMonthEndDate();

  const filtered = state.campaigns.filter(c =>
    !searchTerm || c.name.toLowerCase().includes(searchTerm.toLowerCase()) ||
    (c.jira && c.jira.toLowerCase().includes(searchTerm.toLowerCase())) ||
    (c.type && c.type.toLowerCase().includes(searchTerm.toLowerCase()))
  );

  // 운영 기획전: 오늘~이번달 말일 사이에 운영되는 것
  const activeCampaigns = filtered.filter(c => {
    const end = c.period?.end || '';
    const start = c.period?.start || '';
    return end >= today && start <= monthEnd;
  });

  // 종료 기획전: 종료일이 오늘 이전인 것
  const endedCampaigns = filtered.filter(c => {
    const end = c.period?.end || '';
    return end && end < today;
  });

  if (filtered.length === 0) {
    list.innerHTML = `
      <div class="empty-state">
        <div class="empty-state-icon">📋</div>
        <div class="empty-state-text">
          ${searchTerm ? '검색 결과가 없습니다.' : '기획전을 추가해주세요.'}
        </div>
      </div>
    `;
    return;
  }

  let html = '';

  // 운영 기획전
  if (activeCampaigns.length > 0) {
    const sortedActive = sortActiveCampaigns(activeCampaigns);
    const currentSort = getActiveSortValue();
    html += `<div class="campaign-section active-campaigns">
      <div class="campaign-section-header" onclick="toggleCampaignSection(this)">
        <span class="section-toggle">▼</span> 운영 기획전 (${activeCampaigns.length})
      </div>
      <div class="campaign-section-body">
        <div class="active-sort">
          <select id="activeSortSelect" onchange="onActiveSortChange()">
            <option value="name" ${currentSort === 'name' ? 'selected' : ''}>ㄱㄴㄷ순</option>
            <option value="start" ${currentSort === 'start' ? 'selected' : ''}>시작일순</option>
          </select>
        </div>
        ${sortedActive.map(c => renderCampaignCard(c)).join('')}
      </div>
    </div>`;
  }

  // 종료 기획전
  if (endedCampaigns.length > 0) {
    const endedYearMonth = getEndedFilterValue();
    const filteredEnded = filterEndedByYearMonth(endedCampaigns, endedYearMonth);
    const yearMonthOptions = getEndedYearMonthOptions(endedCampaigns);

    html += `<div class="campaign-section collapsed">
      <div class="campaign-section-header" onclick="toggleCampaignSection(this)">
        <span class="section-toggle">▼</span> 종료 기획전 (${filteredEnded.length}/${endedCampaigns.length})
      </div>
      <div class="campaign-section-body">
        <div class="ended-filter">
          <select id="endedYearMonthFilter" onchange="onEndedFilterChange()">
            <option value="all">전체</option>
            ${yearMonthOptions.map(ym => `<option value="${ym}" ${ym === endedYearMonth ? 'selected' : ''}>${ym}</option>`).join('')}
          </select>
        </div>
        ${filteredEnded.map(c => renderCampaignCard(c, true)).join('')}
      </div>
    </div>`;
  }

  list.innerHTML = html;

  // 드래그 이벤트 연결
  list.querySelectorAll('.campaign-card').forEach(card => {
    card.addEventListener('dragstart', handleCampaignDragStart);
    card.addEventListener('dragend', handleCampaignDragEnd);
  });
}

function getMonthEndDate() {
  const now = new Date();
  const lastDay = new Date(now.getFullYear(), now.getMonth() + 1, 0);
  return formatDateISO(lastDay);
}

function renderCampaignCard(c, isEnded = false) {
  const color = TYPE_COLORS[c.type] || '#6b7280';
  const jiraLink = c.jira ? `<a href="http://jira.lge.com/issue/browse/ONMKT-${c.jira}" target="_blank" class="jira-link" onclick="event.stopPropagation()">ONMKT-${escapeHtml(c.jira)}</a>` : '';
  return `
    <div class="campaign-card ${isEnded ? 'ended' : ''}" draggable="${!isEnded}" data-id="${c.id}">
      <div class="campaign-color" style="background:${color}"></div>
      <div class="campaign-info">
        <div class="campaign-name">${escapeHtml(c.name)}</div>
        <div class="campaign-meta">
          <span class="campaign-type">${escapeHtml(c.type || '')}</span>
          ${c.category ? `<span class="campaign-category">${escapeHtml(c.category)}</span>` : ''}
          ${jiraLink}
        </div>
        <div class="campaign-period">
          ${c.period?.start || ''} ~ ${c.period?.end || ''}
        </div>
      </div>
      <div class="campaign-actions">
        <button type="button" onclick="editCampaign('${c.id}')" title="수정">✎</button>
        <button type="button" onclick="deleteCampaign('${c.id}')" title="삭제">×</button>
      </div>
    </div>
  `;
}

function toggleCampaignSection(header) {
  header.closest('.campaign-section').classList.toggle('collapsed');
}

// 운영 기획전 정렬
let activeSortValue = 'name';

function getActiveSortValue() {
  return activeSortValue;
}

function sortActiveCampaigns(campaigns) {
  const sorted = [...campaigns];
  if (activeSortValue === 'name') {
    sorted.sort((a, b) => (a.name || '').localeCompare(b.name || '', 'ko'));
  } else if (activeSortValue === 'start') {
    sorted.sort((a, b) => (a.period?.start || '').localeCompare(b.period?.start || ''));
  }
  return sorted;
}

function onActiveSortChange() {
  const sel = document.getElementById('activeSortSelect');
  if (sel) {
    activeSortValue = sel.value;
    renderCampaigns(document.getElementById('campaignSearch').value);
  }
}

// 종료 기획전 필터
let endedFilterValue = 'all';

function getEndedFilterValue() {
  return endedFilterValue;
}

function getEndedYearMonthOptions(endedCampaigns) {
  const ymSet = new Set();
  endedCampaigns.forEach(c => {
    const end = c.period?.end || '';
    if (end) {
      const ym = end.substring(0, 7); // YYYY-MM
      ymSet.add(ym);
    }
  });
  return Array.from(ymSet).sort().reverse();
}

function filterEndedByYearMonth(endedCampaigns, yearMonth) {
  if (yearMonth === 'all') return endedCampaigns;
  return endedCampaigns.filter(c => {
    const end = c.period?.end || '';
    return end.startsWith(yearMonth);
  });
}

function onEndedFilterChange() {
  const select = document.getElementById('endedYearMonthFilter');
  endedFilterValue = select.value;
  renderCampaigns(document.getElementById('campaignSearch').value);
}

// 월별 캘린더 렌더링
function renderCalendar() {
  const container = document.getElementById('calendarContainer');

  // 현재 영역의 구좌만 필터링
  const areaSlots = state.slots.filter(s => s.area === state.currentArea);

  // 그룹별로 분류
  const groups = {};
  areaSlots.forEach(slot => {
    const group = slot.group || '기타';
    if (!groups[group]) groups[group] = [];
    groups[group].push(slot);
  });

  // 월의 주 계산
  const weeks = getMonthWeeks(state.currentYear, state.currentMonth);

  container.innerHTML = Object.entries(groups).map(([groupName, slots]) => `
    <div class="slot-group">
      <div class="slot-group-header" onclick="toggleSlotGroup(this)">
        <h3><span class="slot-group-toggle">▼</span> ${escapeHtml(groupName)}</h3>
        <span class="slot-group-count">${slots.length}개 구좌</span>
      </div>
      <div class="slot-group-body">
        ${renderCalendarTable(slots, weeks, groupName)}
      </div>
    </div>
  `).join('');

  // 드롭 이벤트 연결
  container.querySelectorAll('.calendar-cell').forEach(cell => {
    cell.addEventListener('dragover', handleCellDragOver);
    cell.addEventListener('dragleave', handleCellDragLeave);
    cell.addEventListener('drop', handleCellDrop);
  });

  // 오늘 날짜로 스크롤 (첫 번째 그룹 기준)
  scrollToToday();
}

function scrollToToday() {
  const todayCell = document.querySelector('.calendar-cell.today');
  if (!todayCell) return;

  const wrapper = todayCell.closest('.calendar-scroll-wrapper');
  if (!wrapper) return;

  // 오늘 셀 위치에서 약간 왼쪽으로 (여유 공간)
  const cellLeft = todayCell.offsetLeft;
  const scrollPos = Math.max(0, cellLeft - 150);
  wrapper.scrollLeft = scrollPos;
}

function getMonthWeeks(year, month) {
  const weeks = [];
  const firstDay = new Date(year, month, 1);
  const lastDay = new Date(year, month + 1, 0);

  // 첫 주의 월요일 찾기
  let currentMonday = getMonday(firstDay);

  while (currentMonday <= lastDay || weeks.length < 5) {
    const week = [];
    for (let i = 0; i < 7; i++) {
      const d = addDays(currentMonday, i);
      week.push({
        date: d,
        dateStr: formatDateISO(d),
        day: d.getDate(),
        isCurrentMonth: d.getMonth() === month,
        isToday: isToday(d),
        isWeekend: isWeekend(d),
      });
    }
    weeks.push(week);
    currentMonday = addDays(currentMonday, 7);

    // 다음 달로 완전히 넘어가면 중단
    if (currentMonday.getMonth() !== month && currentMonday > lastDay) break;
  }

  return weeks;
}

function renderCalendarTable(slots, weeks, groupName = '') {
  const isCategory = groupName === '특정제품';
  const headerLabel = isCategory ? '카테고리' : '순서';

  return `
    <div class="calendar-scroll-wrapper">
      <table class="calendar-table">
        <thead>
          <tr>
            <th class="th-order" rowspan="2">${headerLabel}</th>
            ${weeks.map((week, wi) => `
              <th colspan="7" style="background:var(--surface-2)">
                ${wi + 1}주차 (${week[0].date.getMonth() + 1}/${week[0].day} ~ ${week[6].date.getMonth() + 1}/${week[6].day})
              </th>
            `).join('')}
          </tr>
          <tr>
            ${weeks.map(week => week.map(d => `
              <th class="${d.date.getDay() === 0 ? 'sun' : d.date.getDay() === 6 ? 'sat' : ''}">
                ${WEEKDAYS[d.date.getDay()]}
              </th>
            `).join('')).join('')}
          </tr>
        </thead>
        <tbody>
          ${slots.map((slot, idx) => `
            <tr class="calendar-slot-row" data-slot="${slot.id}">
              <td class="td-order">${isCategory ? (slot.category || slot.name || '') : (slot.order || '')}</td>
              ${weeks.map(week => week.map(d => {
                const dayOfWeek = d.date.getDay();
                const holiday = isHoliday(d.dateStr);
                const cellClasses = [
                  'calendar-cell',
                  d.isToday ? 'today' : '',
                  d.isWeekend ? 'weekend' : '',
                  !d.isCurrentMonth ? 'other-month' : '',
                  dayOfWeek === 0 ? 'sun' : '',
                  dayOfWeek === 6 ? 'sat' : '',
                  holiday ? 'holiday' : '',
                ].filter(Boolean).join(' ');

                const scheduleBar = renderScheduleBar(slot.id, d.dateStr);

                return `
                  <td class="${cellClasses}" data-date="${d.dateStr}" data-slot="${slot.id}">
                    <span class="calendar-day-num">${d.day}</span>
                    ${scheduleBar}
                  </td>
                `;
              }).join('')).join('')}
            </tr>
          `).join('')}
        </tbody>
      </table>
    </div>
  `;
}

function renderScheduleBar(slotId, dateStr) {
  const items = state.schedule.filter(s =>
    s.slotId === slotId &&
    s.start <= dateStr &&
    s.end >= dateStr
  );

  return items.map(item => {
    const campaign = state.campaigns.find(c => c.id === item.campaignId);
    if (!campaign) return '';

    const color = TYPE_COLORS[campaign.type] || '#949494';
    const textColor = getTextColor(campaign.type);
    const isStart = item.start === dateStr;
    const isEnd = item.end === dateStr;
    const posClass = isStart && isEnd ? 'single' : isStart ? 'start' : isEnd ? 'end' : 'middle';
    const modifiedClass = item.modified ? 'modified' : '';

    // 기획전 기간 벗어남 체크
    const campStart = campaign.period?.start || '';
    const campEnd = campaign.period?.end || '';
    const isOutOfRange = (campStart && item.start < campStart) || (campEnd && item.end > campEnd);
    const outOfRangeClass = isOutOfRange ? 'out-of-range' : '';

    return `
      <div class="calendar-bar ${posClass} ${modifiedClass} ${outOfRangeClass}"
           style="background:${color}; color:${isOutOfRange ? '#FD312E' : textColor}"
           data-id="${item.id}"
           data-campaign="${campaign.id}"
           title="${escapeHtml(campaign.name)} (${item.start} ~ ${item.end})${item.modified ? ' [수정됨]' : ''}"
           onclick="showScheduleDetail('${item.id}')"
           ondblclick="deleteScheduleItem('${item.id}')">
        ${(isStart || isEnd) ? escapeHtml(campaign.name) : ''}
      </div>
    `;
  }).join('');
}

// 구좌 그룹 토글
function toggleSlotGroup(header) {
  header.closest('.slot-group').classList.toggle('collapsed');
}

// 기획전 모달
function openCampaignModal(campaign = null) {
  state.editingCampaign = campaign;
  document.getElementById('modalTitle').textContent = campaign ? '기획전 수정' : '기획전 추가';
  document.getElementById('campName').value = campaign?.name || '';
  document.getElementById('campType').value = campaign?.type || '';
  document.getElementById('campCategory').value = campaign?.category || '';
  document.getElementById('campJira').value = campaign?.jira || '';
  document.getElementById('campEventNo').value = campaign?.eventNo || '';
  document.getElementById('campStart').value = campaign?.period?.start || '';
  document.getElementById('campEnd').value = campaign?.period?.end || '';
  document.getElementById('campMemo').value = campaign?.memo || '';
  document.getElementById('memoCount').textContent = (campaign?.memo || '').length;

  // 기획전번호 URL 링크 표시
  const eventVal = campaign?.eventNo || '';
  const linkEl = document.getElementById('eventLink');
  const anchorEl = document.getElementById('eventLinkAnchor');
  if (eventVal) {
    const fullUrl = getEventUrl(eventVal);
    linkEl.style.display = 'block';
    anchorEl.href = fullUrl;
    anchorEl.textContent = fullUrl;
  } else {
    linkEl.style.display = 'none';
  }

  document.getElementById('campaignModal').style.display = 'flex';
}

function closeCampaignModal() {
  document.getElementById('campaignModal').style.display = 'none';
  state.editingCampaign = null;
}

async function saveCampaign() {
  const data = {
    name: document.getElementById('campName').value,
    type: document.getElementById('campType').value,
    category: document.getElementById('campCategory').value,
    jira: document.getElementById('campJira').value,
    eventNo: document.getElementById('campEventNo').value,
    period: {
      start: document.getElementById('campStart').value,
      end: document.getElementById('campEnd').value,
    },
    memo: document.getElementById('campMemo').value,
  };

  try {
    if (state.editingCampaign) {
      await fetch(`/api/campaigns/${state.editingCampaign.id}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
    } else {
      await fetch('/api/campaigns', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data),
      });
    }
    closeCampaignModal();
  } catch (e) {
    console.error('저장 실패:', e);
  }
}

function editCampaign(id) {
  const campaign = state.campaigns.find(c => c.id === id);
  if (campaign) openCampaignModal(campaign);
}

async function deleteCampaign(id) {
  if (!confirm('이 기획전을 삭제하시겠습니까?')) return;
  try {
    await fetch(`/api/campaigns/${id}`, { method: 'DELETE' });
  } catch (e) {
    console.error('삭제 실패:', e);
  }
}

async function deleteScheduleItem(id) {
  if (!confirm('이 스케줄을 삭제하시겠습니까?')) return;
  try {
    await fetch(`/api/schedule/${id}`, { method: 'DELETE' });
  } catch (e) {
    console.error('삭제 실패:', e);
  }
}

// 스케줄 상세 보기
// 현재 보고 있는 스케줄 ID
let currentDetailScheduleId = null;

function showScheduleDetail(scheduleId) {
  const item = state.schedule.find(s => s.id === scheduleId);
  if (!item) return;

  const campaign = state.campaigns.find(c => c.id === item.campaignId);
  if (!campaign) return;

  currentDetailScheduleId = scheduleId;

  const slot = state.slots.find(s => s.id === item.slotId);
  const color = TYPE_COLORS[campaign.type] || '#949494';
  const jiraUrl = campaign.jira ? `http://jira.lge.com/issue/browse/ONMKT-${campaign.jira}` : '';

  const modal = document.getElementById('detailModal');
  document.getElementById('detailColor').style.background = color;
  document.getElementById('detailName').textContent = campaign.name;
  document.getElementById('detailType').textContent = campaign.type || '-';
  document.getElementById('detailCategory').textContent = campaign.category || '-';
  document.getElementById('detailJira').innerHTML = campaign.jira
    ? `<a href="${jiraUrl}" target="_blank">ONMKT-${campaign.jira}</a>`
    : '-';
  const eventUrl = campaign.eventNo ? getEventUrl(campaign.eventNo) : '';
  document.getElementById('detailEventNo').innerHTML = campaign.eventNo
    ? `<a href="${eventUrl}" target="_blank">${eventUrl}</a>`
    : '-';
  document.getElementById('detailPeriod').textContent = `${campaign.period?.start || ''} ~ ${campaign.period?.end || ''}`;
  document.getElementById('detailSlot').textContent = slot
    ? (slot.category ? `${slot.group} - ${slot.category}` : `${slot.group} ${slot.order}순위`)
    : item.slotId;

  // 노출 기간 수정 가능하게 input으로 표시
  document.getElementById('detailSchedStart').value = item.start || '';
  document.getElementById('detailSchedEnd').value = item.end || '';
  document.getElementById('detailMemo').textContent = campaign.memo || '-';

  // 수정됨 표시 여부에 따라 확인 버튼 표시
  const confirmBtn = document.getElementById('detailConfirmBtn');
  if (item.modified) {
    confirmBtn.style.display = 'inline-block';
  } else {
    confirmBtn.style.display = 'none';
  }

  modal.style.display = 'flex';
}

function closeDetailModal() {
  document.getElementById('detailModal').style.display = 'none';
  currentDetailScheduleId = null;
}

async function updateSchedulePeriod() {
  if (!currentDetailScheduleId) return;

  const start = document.getElementById('detailSchedStart').value;
  const end = document.getElementById('detailSchedEnd').value;

  if (!start || !end) {
    alert('시작일과 종료일을 모두 입력해주세요.');
    return;
  }

  if (start > end) {
    alert('종료일은 시작일보다 이후여야 합니다.');
    return;
  }

  try {
    await fetch(`/api/schedule/${currentDetailScheduleId}`, {
      method: 'PUT',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ start, end }),
    });
    closeDetailModal();
  } catch (e) {
    console.error('수정 실패:', e);
    alert('수정에 실패했습니다.');
  }
}

async function confirmScheduleModification() {
  if (!currentDetailScheduleId) return;

  try {
    await fetch(`/api/schedule/${currentDetailScheduleId}/confirm`, {
      method: 'POST',
    });
    closeDetailModal();
  } catch (e) {
    console.error('확인 실패:', e);
  }
}

async function deleteScheduleItem() {
  if (!currentDetailScheduleId) return;

  if (!confirm('이 스케줄을 삭제하시겠습니까?')) return;

  try {
    await fetch(`/api/schedule/${currentDetailScheduleId}`, {
      method: 'DELETE',
    });
    closeDetailModal();
  } catch (e) {
    console.error('삭제 실패:', e);
    alert('삭제에 실패했습니다.');
  }
}

// 엑셀 모달
let pendingExcelData = null;

function openExcelModal() {
  document.getElementById('excelModal').style.display = 'flex';
  document.getElementById('uploadArea').style.display = 'block';
  document.getElementById('uploadPreview').style.display = 'none';
  document.getElementById('uploadConfirmBtn').disabled = true;
  document.getElementById('excelFile').value = '';
  pendingExcelData = null;
}

function closeExcelModal() {
  document.getElementById('excelModal').style.display = 'none';
  pendingExcelData = null;
}

async function handleExcelFile(file) {
  if (!file.name.match(/\.(xlsx|xls)$/i)) {
    alert('엑셀 파일(.xlsx, .xls)만 업로드 가능합니다.');
    return;
  }

  const formData = new FormData();
  formData.append('file', file);

  try {
    const res = await fetch('/api/upload/preview', {
      method: 'POST',
      body: formData,
    });
    const data = await res.json();

    if (data.error) {
      alert(data.error);
      return;
    }

    pendingExcelData = data.campaigns;
    document.getElementById('uploadArea').style.display = 'none';
    document.getElementById('uploadPreview').style.display = 'block';
    document.getElementById('uploadFileName').textContent = file.name;
    document.getElementById('uploadRowCount').textContent = `${data.campaigns.length}개 기획전 인식됨`;
    document.getElementById('uploadConfirmBtn').disabled = false;
  } catch (e) {
    alert('파일 처리 중 오류가 발생했습니다.');
    console.error(e);
  }
}

async function confirmExcelUpload() {
  if (!pendingExcelData || !pendingExcelData.length) return;

  try {
    const res = await fetch('/api/upload/confirm', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ campaigns: pendingExcelData }),
    });
    const data = await res.json();
    closeExcelModal();
    let msg = `${data.added}개 기획전이 추가되었습니다.`;
    if (data.skipped > 0) {
      msg += `\n(중복 ${data.skipped}개 제외)`;
    }
    alert(msg);
  } catch (e) {
    alert('업로드 중 오류가 발생했습니다.');
    console.error(e);
  }
}

function downloadTemplate() {
  window.location.href = '/api/template';
}

function exportScheduleToExcel() {
  window.location.href = `/api/export?year=${currentYear}&month=${currentMonth}&area=${currentArea}`;
}

// 드래그 앤 드롭
let draggedCampaignId = null;

function handleCampaignDragStart(e) {
  draggedCampaignId = e.target.dataset.id;
  e.target.classList.add('dragging');
}

function handleCampaignDragEnd(e) {
  e.target.classList.remove('dragging');
  draggedCampaignId = null;
}

function handleCellDragOver(e) {
  e.preventDefault();
  e.currentTarget.classList.add('drop-target');
}

function handleCellDragLeave(e) {
  e.currentTarget.classList.remove('drop-target');
}

async function handleCellDrop(e) {
  e.preventDefault();
  e.currentTarget.classList.remove('drop-target');

  if (!draggedCampaignId) return;

  const cell = e.currentTarget;
  const slotId = cell.dataset.slot;
  const date = cell.dataset.date;

  const campaign = state.campaigns.find(c => c.id === draggedCampaignId);
  if (!campaign) return;

  const slot = state.slots.find(s => s.id === slotId);

  // 노출 기간 설정 모달 열기
  openScheduleModal(campaign, slot, date);
}

// 노출 기간 설정 모달
let pendingSchedule = null;

function openScheduleModal(campaign, slot, dropDate) {
  pendingSchedule = {
    campaignId: campaign.id,
    slotId: slot.id,
  };

  const color = TYPE_COLORS[campaign.type] || '#949494';
  document.getElementById('schedCampColor').style.background = color;
  document.getElementById('schedCampName').textContent = campaign.name;
  document.getElementById('schedCampPeriod').textContent =
    `기획전 기간: ${campaign.period?.start || '-'} ~ ${campaign.period?.end || '-'}`;
  document.getElementById('schedSlotName').textContent = slot.category
    ? `배치 구좌: ${slot.group} - ${slot.category}`
    : `배치 구좌: ${slot.group} ${slot.order}순위`;

  // 기본값: 드롭한 날짜를 시작일로, 기획전 종료일 또는 +6일을 종료일로
  document.getElementById('schedStart').value = dropDate;
  document.getElementById('schedEnd').value = campaign.period?.end || formatDateISO(addDays(new Date(dropDate), 6));

  document.getElementById('scheduleModal').style.display = 'flex';
}

function closeScheduleModal() {
  document.getElementById('scheduleModal').style.display = 'none';
  pendingSchedule = null;
}

async function confirmSchedule() {
  if (!pendingSchedule) return;

  const start = document.getElementById('schedStart').value;
  const end = document.getElementById('schedEnd').value;

  if (!start || !end) {
    alert('시작일과 종료일을 모두 입력해주세요.');
    return;
  }

  if (start > end) {
    alert('종료일은 시작일보다 이후여야 합니다.');
    return;
  }

  try {
    const res = await fetch('/api/schedule', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        campaignId: pendingSchedule.campaignId,
        slotId: pendingSchedule.slotId,
        start,
        end,
      }),
    });
    const data = await res.json();
    if (!res.ok) {
      alert(data.error || '스케줄 추가에 실패했습니다.');
      return;
    }
    closeScheduleModal();
  } catch (e) {
    console.error('스케줄 추가 실패:', e);
    alert('스케줄 추가에 실패했습니다.');
  }
}

// 유틸리티
function escapeHtml(str) {
  return String(str || '')
    .replace(/&/g, '&amp;')
    .replace(/</g, '&lt;')
    .replace(/>/g, '&gt;')
    .replace(/"/g, '&quot;');
}

// ---- 메모 기능 ----

function updateMemoButton() {
  const btn = document.getElementById('memoBtn');
  const unconfirmedCount = state.memos.filter(m => !m.confirmed).length;
  if (unconfirmedCount > 0) {
    btn.textContent = `★메모 (${unconfirmedCount})`;
    btn.style.color = '#FD312E';
    btn.style.fontWeight = '600';
  } else {
    btn.textContent = '★메모';
    btn.style.color = '';
    btn.style.fontWeight = '';
  }
}

function openMemoModal() {
  document.getElementById('memoModal').style.display = 'flex';
  renderMemos();
}

function closeMemoModal() {
  document.getElementById('memoModal').style.display = 'none';
  document.getElementById('newMemoContent').value = '';
}

function renderMemos() {
  const list = document.getElementById('memoList');
  const addSection = document.getElementById('memoAddSection');

  if (state.memos.length === 0) {
    list.innerHTML = '<div class="memo-empty">등록된 메모가 없습니다.</div>';
  } else {
    list.innerHTML = state.memos.map(memo => {
      const isUnconfirmed = !memo.confirmed;
      const createdDate = new Date(memo.createdAt).toLocaleString('ko-KR');
      const confirmedInfo = memo.confirmed
        ? `<span style="color:var(--success)">${memo.confirmedBy}님이 확인함</span>`
        : `<span style="color:#FD312E">미확인</span>`;

      return `
        <div class="memo-item ${isUnconfirmed ? 'unconfirmed' : ''}">
          <div class="memo-content">${escapeHtml(memo.content)}</div>
          <div class="memo-meta">
            <span>${memo.createdBy} | ${createdDate} | ${confirmedInfo}</span>
            <div class="memo-actions">
              ${isUnconfirmed ? `<button class="btn-sm btn-outline" onclick="confirmMemo('${memo.id}')">확인완료</button>` : ''}
              <button class="btn-sm btn-outline" onclick="deleteMemo('${memo.id}')">삭제</button>
            </div>
          </div>
        </div>
      `;
    }).join('');
  }

  // 최대 3개일 때 추가 섹션 숨기기
  if (state.memos.length >= 3) {
    addSection.classList.add('hidden');
  } else {
    addSection.classList.remove('hidden');
  }
}

async function addMemo() {
  const content = document.getElementById('newMemoContent').value.trim();
  if (!content) {
    alert('메모 내용을 입력하세요.');
    return;
  }

  try {
    const res = await fetch('/api/memos', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ content }),
    });

    if (!res.ok) {
      const err = await res.json();
      alert(err.error || '메모 추가 실패');
      return;
    }

    document.getElementById('newMemoContent').value = '';
  } catch (e) {
    console.error('메모 추가 실패:', e);
    alert('메모 추가에 실패했습니다.');
  }
}

async function confirmMemo(memoId) {
  try {
    const res = await fetch(`/api/memos/${memoId}/confirm`, {
      method: 'POST',
    });

    if (!res.ok) {
      const err = await res.json();
      alert(err.error || '확인 처리 실패');
      return;
    }
  } catch (e) {
    console.error('메모 확인 실패:', e);
    alert('메모 확인에 실패했습니다.');
  }
}

async function deleteMemo(memoId) {
  if (!confirm('메모를 삭제하시겠습니까?')) return;

  try {
    await fetch(`/api/memos/${memoId}`, {
      method: 'DELETE',
    });
  } catch (e) {
    console.error('메모 삭제 실패:', e);
    alert('메모 삭제에 실패했습니다.');
  }
}

// 앱 시작
document.addEventListener('DOMContentLoaded', init);
