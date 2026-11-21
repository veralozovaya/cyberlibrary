import http from 'k6/http';
import { check, sleep } from 'k6';

export const options = {
  stages: [
    { duration: '15s', target: 120 },   // розрахункове навантаження (1x)
    { duration: '20s', target: 400 },   // ~3.3x від розрахункового
    { duration: '20s', target: 800 },   // ~6.6x від розрахункового
    { duration: '20s', target: 1200 },  // 10x від розрахункового (пік стресу)
    { duration: '15s', target: 0 },     // плавне зниження (відновлення)
  ],
  thresholds: {
    http_req_duration: ['p(95)<300'],
  },
};

export default function () {
  const resValid = http.post('http://127.0.0.1:8000/loans/LN-1/renew');
  check(resValid, {
    'LN-1 status is 200 or 400': (r) => r.status === 200 || r.status === 400,
  });

  const resDebt = http.post('http://127.0.0.1:8000/loans/LN-2/renew');
  check(resDebt, {
    'LN-2 status is 400': (r) => r.status === 400,
  });

  sleep(0.2);
}