import test from 'node:test';
import assert from 'node:assert/strict';
import { securitySummary, reviewStatus, parseIndicators } from './security.js';
import { emailCsp } from './emailPrivacy.js';
test('missing, failed and partial scans cannot be low risk', () => {
 for (const email of [{}, {scam_score:0,status:'failed'}, {scam_score:0,analysis_status:'partial'}, {scam_score:0,status:'fetched'}]) assert.equal(securitySummary(email).level, 'unknown');
});
test('completed analysis describes estimate, not a safety guarantee', () => {
 assert.equal(securitySummary({scam_score:0,analysis_status:'completed'}).label,'Low estimated risk');
 assert.equal(securitySummary({scam_score:90,analysis_status:'partial'}).label,'High estimated risk');
});
test('user decision never erases original risk', () => {
 assert.equal(securitySummary({scam_score:95,user_decision:'safe',analysis_status:'completed'}).level,'high');
 assert.equal(reviewStatus({user_decision:'safe'}),'user_safe');
 assert.equal(reviewStatus({sync_status:'failed'}),'sync_failed');
 assert.equal(reviewStatus({synced_to_gmail:1}),'applied');
});
test('invalid indicators fail closed without crashing inbox', () => {
 assert.deepEqual(parseIndicators('{bad'),[]); assert.deepEqual(parseIndicators('{}'),[]); assert.deepEqual(parseIndicators('["link"]'),['link']);
});
test('privacy blocks all network resources until image consent', () => {
 assert.match(emailCsp(false),/img-src data: cid:/);
 assert.doesNotMatch(emailCsp(false),/https:/);
 assert.match(emailCsp(true),/img-src data: cid: https: http:/);
 assert.match(emailCsp(true),/default-src 'none'/);
 assert.match(emailCsp(true),/style-src 'unsafe-inline'/);
});
