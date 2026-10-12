export type Role = "student" | "admin";

export interface Me {
  role: Role;
  name: string;
  rollNo: string;
}

export interface Room {
  hostelId: string;
  hostel: string;
  hostelName: string;
  room: string;
  floor: number;
  direction: string;
  washroomType: string;
  roomType: string;
  bed: string;
}

export type RoundStatus =
  | "draft" | "open" | "locked" | "running" | "completed" | "cancelled";

export interface StudentRound {
  id: string;
  hostelId: string;
  status: RoundStatus;
  enrolled: boolean;
}

export interface Hostel {
  id: string;
  code: string;
  name: string;
}

export interface AdminRound {
  id: string;
  hostelId: string;
  status: RoundStatus;
}

export interface RoomType {
  roomType: string;
  quantity: number;
}

export interface Priority {
  criterion: string;
  value: string;
  weight: number;
  hard?: boolean;
}

export type RoommateStatus = "pending" | "accepted" | "rejected" | "withdrawn";

export interface RoommateRequest {
  id: string;
  status: RoommateStatus;
  rollNo: string;
  name: string;
  createdAt: string;
}

export interface RoommateState {
  /** The pairing this student asked for, if any. */
  outgoing: RoommateRequest | null;
  /** Asks waiting on this student to answer. */
  incoming: RoommateRequest[];
}

export interface ChainMember {
  studentId: string;
  rollNo: string;
  name: string;
  from: string;
  to: string;
  match: number;
  fromSlotId: string;
  toSlotId: string;
  committed?: boolean;
}

export interface ChainOption {
  optionKind: string;
  chainNo: number;
  members: ChainMember[];
  myMatch: number;
  myFrom: string;
  myTo: string;
  available: boolean;
  takenBy: string[];
}

export type Approval = "pending" | "approved" | "rejected";

export interface ProposalMember {
  position: number;
  studentId: string;
  rollNo: string;
  name: string;
  fromSlotId: string;
  toSlotId: string;
  matchValue: number;
  approval: Approval;
}

export interface Proposal {
  id: string;
  roundId: string | null;
  status: string;
  expiresAt: string;
  settledAt: string | null;
  members: ProposalMember[];
}

export interface RoundSummary {
  status: RoundStatus;
  enrolled: number;
  prioritised: number;
  chains: number;
  withOptions: number;
  proposals: number;
  awaiting: number;
  executed: number;
}

export interface RunResult {
  roundId: string;
  options: number;
  chains: number;
}
