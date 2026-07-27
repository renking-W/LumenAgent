/**
 * 生成 UUID v4。
 *
 * 公网 HTTP 不属于安全上下文，浏览器可能不提供 randomUUID，
 * 此时使用仍可用的 getRandomValues 生成兼容标识。
 */
export function createUuid(): string {
  const cryptoApi = globalThis.crypto
  if (typeof cryptoApi?.randomUUID === 'function') {
    return cryptoApi.randomUUID()
  }
  if (!cryptoApi?.getRandomValues) {
    throw new Error('当前浏览器不支持安全随机数生成')
  }

  const bytes = new Uint8Array(16)
  cryptoApi.getRandomValues(bytes)
  bytes[6] = (bytes[6] & 0x0f) | 0x40
  bytes[8] = (bytes[8] & 0x3f) | 0x80
  const hex = Array.from(bytes, byte => byte.toString(16).padStart(2, '0')).join('')
  return `${hex.slice(0, 8)}-${hex.slice(8, 12)}-${hex.slice(12, 16)}-${hex.slice(16, 20)}-${hex.slice(20)}`
}
