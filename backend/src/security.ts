import { randomBytes, scrypt as scryptCallback, timingSafeEqual, createHash } from 'node:crypto';
import { promisify } from 'node:util';
const scrypt = promisify(scryptCallback);
export async function hashPassword(password: string) {
  const salt = randomBytes(16).toString('hex');
  return salt + ':' + (await scrypt(password,salt,64) as Buffer).toString('hex');
}
export async function verifyPassword(password: string, hash: string) {
  const [salt, key] = hash.split(':');
  const actual = await scrypt(password,salt,64) as Buffer;
  const expected = Buffer.from(key,'hex');
  return expected.length === actual.length && timingSafeEqual(actual,expected);
}
export const token = () => randomBytes(32).toString('base64url');
export const digest = (value: string) => createHash('sha256').update(value).digest('hex');
export class ApiError extends Error { constructor(public statusCode: number,message: string) { super(message); } }
export const fail = (status: number,message: string): never => { throw new ApiError(status,message); };
