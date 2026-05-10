// @ts-nocheck

export const APP_TIME_ZONE = 'Asia/Seoul';

const APP_DATE_TIME_FORMATTER = new Intl.DateTimeFormat('en-US', {
  timeZone: APP_TIME_ZONE,
  year: 'numeric',
  month: '2-digit',
  day: '2-digit',
  hour: '2-digit',
  minute: '2-digit',
  second: '2-digit',
  hourCycle: 'h23',
});

export function getAppNowDate(value = new Date()) {
  const parts = getAppDateTimeParts(value);
  return new Date(parts.year, parts.month - 1, parts.day, parts.hour, parts.minute, parts.second);
}

export function getAppTodayDate(value = new Date()) {
  const parts = getAppDateTimeParts(value);
  return new Date(parts.year, parts.month - 1, parts.day);
}

export function getAppTodayValue(value = new Date()) {
  return formatDateValue(getAppTodayDate(value));
}

export function formatAppDateValue(value) {
  return formatDateValue(getAppTodayDate(new Date(value)));
}

export function formatAppTime(value) {
  if (!value) {
    return '-';
  }
  const parts = getAppDateTimeParts(value);
  return `${String(parts.hour).padStart(2, '0')}:${String(parts.minute).padStart(2, '0')}`;
}

export function formatAppDateTime(value) {
  if (!value) {
    return '-';
  }
  const parts = getAppDateTimeParts(value);
  return `${String(parts.month).padStart(2, '0')}-${String(parts.day).padStart(2, '0')} ${String(parts.hour).padStart(2, '0')}:${String(parts.minute).padStart(2, '0')}`;
}

export function parseDateValue(value) {
  if (!/^\d{4}-\d{2}-\d{2}$/.test(value || '')) {
    return null;
  }

  const [year, month, day] = value.split('-').map(Number);
  return new Date(year, month - 1, day);
}

export function formatDateValue(date) {
  return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
}

export function addDays(date, days) {
  return new Date(date.getFullYear(), date.getMonth(), date.getDate() + days);
}

export function startOfWeek(date) {
  const day = date.getDay();
  const mondayOffset = day === 0 ? -6 : 1 - day;
  return addDays(date, mondayOffset);
}

export function isSameDateValue(value, target) {
  const date = parseDateValue(value);
  if (!date || !target) {
    return false;
  }
  return formatDateValue(date) === formatDateValue(target);
}

export function isRelativeAppDateValue(value, offsetDays) {
  return isSameDateValue(value, addDays(getAppTodayDate(), offsetDays));
}

function getAppDateTimeParts(value) {
  const date = value instanceof Date ? value : new Date(value);
  const result = {};
  for (const part of APP_DATE_TIME_FORMATTER.formatToParts(date)) {
    if (part.type !== 'literal') {
      result[part.type] = Number(part.value);
    }
  }
  return result;
}
