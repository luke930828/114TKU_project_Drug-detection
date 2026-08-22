export const MALICIOUS_INPUT_MESSAGE =
  "偵測到疑似惡意程式碼或攻擊指令，已阻止送出。";

const MALICIOUS_PATTERNS: RegExp[] = [
  /<\s*\/?\s*(?:script|iframe|object|embed|svg|math|style|link|meta)\b/i,
  /<[^>]+\bon[a-z]+\s*=/i,
  /(?:javascript|vbscript)\s*:/i,
  /data\s*:\s*text\/html/i,
  /(?:'|"|`)\s*(?:or|and)\s+(?:'[^']*'|"[^"]*"|\d+)\s*=\s*(?:'[^']*'|"[^"]*"|\d+)/i,
  /\bunion\s+(?:all\s+)?select\b/i,
  /;\s*(?:drop|truncate|alter|delete|insert|update)\s+(?:table|database|from|into)\b/i,
  /\b(?:sleep|benchmark)\s*\(/i,
  /(?:--|#|\/\*)\s*(?:$|select|union|drop|insert|update|delete)/i,
  /(?:;|&&|\|\|)\s*(?:rm|curl|wget|shutdown|reboot|kill|nc|bash|sh)\b/i,
];

export const containsMaliciousInput = (value: string) =>
  MALICIOUS_PATTERNS.some((pattern) => pattern.test(value));

export const hasMaliciousInput = (values: string[]) =>
  values.some(containsMaliciousInput);
