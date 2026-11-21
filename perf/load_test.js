import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  vus: 120,
  duration: '1m',
  thresholds: {
    http_req_duration: ['p(95)<300'],
  },
};

export default function () {
  // 1. Запит на продовження валідної видачі (перші 2 рази -> 200, далі очікувано -> 400)
  const resValid = http.post('http://127.0.0.1:8000/loans/LN-1/renew');
  check(resValid, {
    'LN-1 status is 200 or 400': (r) => r.status === 200 || r.status === 400,
  });

  // 2. Запит на продовження видачі боржника (очікувано -> 400)
  const resDebt = http.post('http://127.0.0.1:8000/loans/LN-2/renew');
  check(resDebt, {
    'LN-2 status is 400': (r) => r.status === 400,
  });

  sleep(0.2);
}