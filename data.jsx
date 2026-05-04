// Sample order data — mixed B2C / B2B cleaning
const ORDERS = [
  { id: 'CO-2451', status: '협력사확인중', received: '04-30 14:22', visit: '05-04', timeWindow: '오전 9-12', team: '미배정', product: '입주청소 (32평)', address: '서울 강남구 도산대로 123 래미안아파트 2304호', customer: '김지원', phone: '010-2*** -4521', amount: 480000, paid: 'partial', photo: 'none', delivered: 'pending' },
  { id: 'CO-2450', status: '사진검수대기', received: '04-29 11:08', visit: '05-02', timeWindow: '오후 2-5', team: '클린파트너스', product: '에어컨 분해세척 4대', address: '서울 마포구 와우산로 88 합정스카이뷰 1102호', customer: '이서연', phone: '010-7*** -1129', amount: 320000, paid: 'paid', photo: 'wait', delivered: 'pending' },
  { id: 'CO-2449', status: '고객전달필요', received: '04-29 09:14', visit: '05-01', timeWindow: '오전 10-1', team: '하우스케어', product: '이사청소 (24평)', address: '경기 성남시 분당구 정자일로 45 정자센트럴 803호', customer: '박민호', phone: '010-3*** -8821', amount: 290000, paid: 'paid', photo: 'approved', delivered: 'pending' },
  { id: 'CO-2448', status: '작업진행', received: '04-28 16:55', visit: '05-02', timeWindow: '오전 9-12', team: '청소플러스', product: '사무실 정기청소 80평', address: '서울 강서구 마곡중앙로 12 마곡테크노타워 18F', customer: '㈜노바테크', phone: '02-***-7700', amount: 1280000, paid: 'paid', photo: 'partial', delivered: 'pending' },
  { id: 'CO-2447', status: '전날안내필요', received: '04-28 13:32', visit: '05-03', timeWindow: '오후 1-4', team: '클린파트너스', product: '입주청소 (45평)', address: '서울 송파구 잠실로 209 잠실리센츠 1812호', customer: '최유진', phone: '010-9*** -3401', amount: 620000, paid: 'partial', photo: 'none', delivered: 'pending' },
  { id: 'CO-2446', status: '서비스완료', received: '04-27 10:10', visit: '04-30', timeWindow: '오전 10-1', team: '하우스케어', product: '준공청소 상가 60평', address: '서울 용산구 한강대로 405 1F', customer: '주식회사 메르시', phone: '02-***-2240', amount: 880000, paid: 'paid', photo: 'approved', delivered: 'done' },
  { id: 'CO-2445', status: '일정확정', received: '04-27 09:45', visit: '05-05', timeWindow: '오전 9-12', team: '청소플러스', product: '에어컨 분해세척 2대', address: '인천 연수구 송도과학로 32 더샵센트럴파크 4012호', customer: '강도윤', phone: '010-4*** -7782', amount: 180000, paid: 'pending', photo: 'none', delivered: 'pending' },
  { id: 'CO-2444', status: '신규접수', received: '04-30 17:48', visit: '미정', timeWindow: '-', team: '미배정', product: '입주청소 문의', address: '서울 서초구 반포대로 217', customer: '윤하늘', phone: '010-8*** -2003', amount: 0, paid: 'pending', photo: 'none', delivered: 'pending' },
  { id: 'CO-2443', status: '상담중', received: '04-30 11:20', visit: '미정', timeWindow: '-', team: '미배정', product: '사무실 정기 견적 요청', address: '서울 영등포구 여의대로 24', customer: '㈜한빛소프트', phone: '02-***-9210', amount: 0, paid: 'pending', photo: 'none', delivered: 'pending' },
  { id: 'CO-2442', status: '취소', received: '04-26 15:32', visit: '04-29', timeWindow: '오후 2-5', team: '하우스케어', product: '이사청소 (28평)', address: '경기 고양시 일산서구 주엽로 12', customer: '오세영', phone: '010-2*** -6611', amount: 270000, paid: 'refund', photo: 'none', delivered: 'cancelled' },
  { id: 'CO-2441', status: '서비스완료', received: '04-26 09:00', visit: '04-29', timeWindow: '오전 10-1', team: '클린파트너스', product: '입주청소 (38평)', address: '서울 성동구 왕십리로 83 센트라스 2105호', customer: '한서윤', phone: '010-6*** -4408', amount: 540000, paid: 'paid', photo: 'approved', delivered: 'done' },
  { id: 'CO-2440', status: '작업예정', received: '04-25 14:00', visit: '05-02', timeWindow: '오전 9-12', team: '청소플러스', product: '준공청소 (54평)', address: '서울 동작구 사당로 110 푸르지오써밋 3201호', customer: '정태욱', phone: '010-5*** -9912', amount: 720000, paid: 'paid', photo: 'none', delivered: 'pending' },
];

const TIMELINE_2450 = [
  { time: '04-29 11:08', who: '시스템', text: '주문 접수 (홈페이지 폼)' },
  { time: '04-29 11:42', who: '관리자 전소영', text: '상담 통화 — 4대 분해세척 확정, 가격 320,000원 안내' },
  { time: '04-29 14:10', who: '관리자 전소영', text: '협력사 클린파트너스 배정 요청' },
  { time: '04-29 16:33', who: '클린파트너스', text: '확인 완료 — 5/2 오후 2시 가능' },
  { time: '04-29 16:34', who: '관리자 전소영', text: '일정확정 처리 + 고객 안내 발송' },
  { time: '05-01 18:00', who: '시스템', text: '전날 안내 알림톡 자동 발송' },
  { time: '05-02 14:08', who: '협력사', text: '작업 시작' },
  { time: '05-02 17:21', who: '협력사', text: '비포 8장 / 애프터 8장 업로드 완료' },
  { time: '05-02 17:22', who: '시스템', text: '사진검수 대기 큐로 이동' },
];

const QUEUES = [
  { key: 'partner_pending',  title: '협력사 확인 필요', count: 4, tone: 'warn',    icon: 'clock',    desc: '배정 후 확인 미수신 24h+' },
  { key: 'tomorrow_notify',  title: '내일 안내 발송 필요', count: 7, tone: 'warn',    icon: 'send',     desc: '5월 3일 작업 예정' },
  { key: 'today_work',       title: '오늘 작업 예정',   count: 5, tone: 'info',    icon: 'truck',    desc: '진행 중 1건 포함' },
  { key: 'photo_review',     title: '사진 검수 대기',   count: 6, tone: 'purple',  icon: 'image',    desc: '평균 대기 3.4시간' },
  { key: 'customer_deliver', title: '고객 전달 필요',   count: 3, tone: 'warn',    icon: 'sparkles', desc: '검수 완료 · 미발송' },
  { key: 'payment_check',    title: '결제 확인 필요',   count: 2, tone: 'danger',  icon: 'creditCard', desc: '잔금 미확인' },
];

const KPI = [
  { label: '오늘 작업 예정', value: 5, delta: '+2',  trend: [3,4,3,5,6,4,5], tone: 'info' },
  { label: '내일 안내 대상', value: 7, delta: '+1',  trend: [5,6,4,5,7,6,7], tone: 'warn' },
  { label: '사진 검수 대기', value: 6, delta: '-2',  trend: [9,8,7,8,6,7,6], tone: 'purple' },
  { label: '고객 전달 필요', value: 3, delta: '0',   trend: [2,3,2,3,4,3,3], tone: 'warn' },
  { label: '결제 확인 필요', value: 2, delta: '-1',  trend: [4,3,3,2,3,2,2], tone: 'danger' },
  { label: '이번 달 완료',   value: 142, delta: '+18%', trend: [80,95,105,118,125,135,142], tone: 'success', suffix: '건' },
  { label: '이번 달 계약금액', value: '₩ 8,420만', delta: '+22%', trend: [40,55,62,70,78,82,84], tone: 'brand' },
];

const TODAY_JOBS = [
  { id: 'CO-2448', time: '오전 9-12', product: '사무실 정기청소 80평', addr: '서울 강서구 마곡테크노타워', team: '청소플러스', status: '작업진행' },
  { id: 'CO-2452', time: '오전 10-1', product: '입주청소 28평', addr: '서울 노원구 상계로 88', team: '하우스케어', status: '작업예정' },
  { id: 'CO-2453', time: '오후 1-4',  product: '에어컨 분해세척 3대', addr: '경기 성남시 분당구 백현로', team: '클린파트너스', status: '작업예정' },
  { id: 'CO-2450', time: '오후 2-5',  product: '에어컨 분해세척 4대', addr: '서울 마포구 합정스카이뷰', team: '클린파트너스', status: '사진검수대기' },
  { id: 'CO-2454', time: '오후 3-6',  product: '준공청소 상가 40평', addr: '서울 종로구 종로 105', team: '청소플러스', status: '작업예정' },
];

const TOMORROW_JOBS = [
  { id: 'CO-2447', time: '오후 1-4',  product: '입주청소 45평', addr: '서울 송파구 잠실리센츠', team: '클린파트너스', status: '전날안내필요' },
  { id: 'CO-2455', time: '오전 9-12', product: '이사청소 32평', addr: '서울 강동구 천호대로', team: '하우스케어', status: '전날안내필요' },
  { id: 'CO-2456', time: '오전 10-1', product: '에어컨 분해세척 2대', addr: '인천 부평구 부평대로', team: '클린파트너스', status: '일정확정' },
];

const RECENT_PHOTOS = [
  { id: 'CO-2450', label: '에어컨 4대 · 합정', count: '비포 8 / 애프터 8', time: '5분 전', tone: 'wait' },
  { id: 'CO-2446', label: '준공청소 · 한강로', count: '비포 12 / 애프터 14', time: '32분 전', tone: 'approved' },
  { id: 'CO-2441', label: '입주청소 · 성수', count: '비포 6 / 애프터 6', time: '1시간 전', tone: 'approved' },
  { id: 'CO-2448', label: '사무실 80평 · 마곡', count: '비포 4 / 애프터 0', time: '진행중', tone: 'partial' },
];

const RECENT_SENDS = [
  { time: '14:22', kind: '일정확정', target: '김지원 010-2***-4521', via: '알림톡', state: 'delivered' },
  { time: '13:08', kind: '전날안내', target: '한서윤 010-6***-4408', via: '알림톡', state: 'delivered' },
  { time: '11:55', kind: '협력사배정', target: '클린파트너스 박정훈', via: 'SMS', state: 'delivered' },
  { time: '10:33', kind: '완료사진', target: '주식회사 메르시', via: '알림톡', state: 'read' },
  { time: '09:21', kind: '잔금안내', target: '강도윤 010-4***-7782', via: '알림톡', state: 'failed' },
];

Object.assign(window, { ORDERS, QUEUES, KPI, TODAY_JOBS, TOMORROW_JOBS, RECENT_PHOTOS, RECENT_SENDS, TIMELINE_2450 });
