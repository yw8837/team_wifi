import { afterEach, describe, expect, it, vi } from "vitest";
import { readPublic } from "./release-data";
import { ApiError } from "./api";
const mocked=vi.hoisted(()=>({api:vi.fn()}));
vi.mock("./api",async()=>{const actual=await vi.importActual<typeof import("./api")>("./api");return {...actual,api:mocked.api};});
afterEach(()=>{vi.useRealTimers();mocked.api.mockReset();});
describe("bounded public cold start reads",()=>{
 it("retries a transient read once and succeeds",async()=>{vi.useFakeTimers();mocked.api.mockRejectedValueOnce(new ApiError(503,"starting")).mockResolvedValueOnce([]);const request=readPublic("/release/offers");await vi.advanceTimersByTimeAsync(700);expect(await request).toEqual([]);expect(mocked.api).toHaveBeenCalledTimes(2);expect(mocked.api.mock.calls.every(call=>call.length===1)).toBe(true);});
 it("does not retry authentication failures",async()=>{mocked.api.mockRejectedValue(new ApiError(401,"login"));await expect(readPublic("/release/offers")).rejects.toMatchObject({status:401});expect(mocked.api).toHaveBeenCalledTimes(1);});
 it("does not loop after two transient failures",async()=>{vi.useFakeTimers();mocked.api.mockRejectedValue(new ApiError(0,"offline"));const request=expect(readPublic("/config")).rejects.toMatchObject({status:0});await vi.advanceTimersByTimeAsync(700);await request;expect(mocked.api).toHaveBeenCalledTimes(2);});
});
