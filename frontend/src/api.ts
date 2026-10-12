/** One place that knows how to talk to the FastAPI backend.
 *
 * Session auth is a cookie the server sets, so nothing here carries a
 * token. A 401 means the cookie is gone or expired: `ApiError.unauthorized`
 * lets callers send the viewer back to the sign-in screen instead of
 * showing them an error they cannot act on.
 */
import type {
  AdminRound, ChainOption, Hostel, Me, Priority, Proposal, Room, RoomType,
  RoommateRequest, RoommateState, RoundSummary, RunResult, StudentRound,
} from "./types";

export class ApiError extends Error {
  readonly status: number;
  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
  get unauthorized() {
    return this.status === 401;
  }
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    // FastAPI puts the readable reason in `detail`; fall back to the
    // status line when a proxy or a crash returns something else.
    let detail = `Request failed (${res.status})`;
    try {
      const body = await res.json();
      if (typeof body?.detail === "string") detail = body.detail;
    } catch {
      /* not JSON */
    }
    throw new ApiError(res.status, detail);
  }
  if (res.status === 204) return undefined as T;
  return (await res.json()) as T;
}

const post = <T>(path: string, body?: unknown) =>
  request<T>(path, { method: "POST", body: body === undefined ? undefined : JSON.stringify(body) });
const put = <T>(path: string, body: unknown) =>
  request<T>(path, { method: "PUT", body: JSON.stringify(body) });

export const api = {
  login: (identifier: string, password: string) =>
    post<Me>("/api/auth/login", { identifier, password }),
  logout: () => post<{ ok: boolean }>("/api/auth/logout"),
  me: () => request<Me>("/api/auth/me"),

  student: {
    /** 404 here means "no room on file", which is a state the page shows
     *  rather than an error, so it resolves to null. */
    room: async (): Promise<Room | null> => {
      try {
        return await request<Room>("/api/student/room");
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    round: async (): Promise<StudentRound | null> => {
      try {
        const d = await request<{ round: StudentRound | null }>("/api/student/round");
        return d.round;
      } catch (err) {
        if (err instanceof ApiError && err.status === 404) return null;
        throw err;
      }
    },
    enroll: (roundId: string, enrolled: boolean) =>
      post<{ ok: boolean }>(`/api/student/round/${roundId}/enroll`, { enrolled }),
    roomTypes: (roundId: string) =>
      request<{ roomTypes: RoomType[] }>(`/api/student/round/${roundId}/room-types`)
        .then((d) => d.roomTypes),
    priorities: (roundId: string) =>
      request<{ priorities: Priority[] }>(`/api/student/round/${roundId}/priorities`)
        .then((d) => d.priorities),
    savePriorities: (roundId: string, priorities: Priority[]) =>
      put<{ ok: boolean }>(`/api/student/round/${roundId}/priorities`, { priorities }),
    roommate: (roundId: string) =>
      request<RoommateState>(`/api/student/round/${roundId}/roommate`),
    requestRoommate: (roundId: string, rollNo: string) =>
      post<RoommateRequest>(`/api/student/round/${roundId}/roommate`, { rollNo }),
    withdrawRoommate: (roundId: string) =>
      request<{ ok: boolean }>(`/api/student/round/${roundId}/roommate`, { method: "DELETE" }),
    answerRoommate: (requestId: string, accept: boolean) =>
      post<{ status: string }>(`/api/student/roommate-requests/${requestId}/respond`, { accept }),

    results: (roundId: string) =>
      request<{ ready: boolean; options: ChainOption[] }>(`/api/student/round/${roundId}/results`),
    offer: (roundId: string, optionKind: string, chainNo: number) =>
      post<{ proposalId: string }>(`/api/student/round/${roundId}/chains/offer`, { optionKind, chainNo }),
    proposals: () =>
      request<{ proposals: Proposal[] }>("/api/student/proposals").then((d) => d.proposals),
    respond: (proposalId: string, accept: boolean) =>
      post<{ status: string }>(`/api/student/proposals/${proposalId}/respond`, { accept }),
  },

  admin: {
    hostels: () => request<{ hostels: Hostel[] }>("/api/admin/hostels").then((d) => d.hostels),
    round: (hostelId: string) =>
      request<{ round: AdminRound | null }>(`/api/admin/hostels/${hostelId}/round`)
        .then((d) => d.round),
    roomTypes: (hostelId: string) =>
      request<{ roomTypes: RoomType[] }>(`/api/admin/hostels/${hostelId}/room-types`)
        .then((d) => d.roomTypes),
    saveRoomType: (hostelId: string, roomType: string, quantity: number) =>
      put<{ ok: boolean }>(`/api/admin/hostels/${hostelId}/room-types`, { roomType, quantity }),
    createRound: (hostelId: string) =>
      post<{ roundId: string }>("/api/admin/rounds", { hostelId }).then((d) => d.roundId),
    openRound: (roundId: string) => post<{ ok: boolean }>(`/api/admin/rounds/${roundId}/open`),
    lockAndRun: (roundId: string, k: number, maxChain: number | null) => {
      const q = new URLSearchParams({ k: String(k) });
      if (maxChain !== null) q.set("max_chain", String(maxChain));
      return post<RunResult>(`/api/admin/rounds/${roundId}/lock-and-run?${q}`);
    },
    summary: (roundId: string) =>
      request<{ summary: RoundSummary }>(`/api/admin/rounds/${roundId}/summary`)
        .then((d) => d.summary),
    proposals: (roundId: string) =>
      request<{ proposals: Proposal[] }>(`/api/admin/rounds/${roundId}/proposals`)
        .then((d) => d.proposals),
  },
};
