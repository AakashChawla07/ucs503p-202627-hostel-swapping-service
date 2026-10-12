import type { ChainOption } from "../types";

interface Props {
  option: ChainOption;
  rank: number;
  myRollNo: string;
  blockedByOwnOffer: boolean;
  onOffer: (option: ChainOption) => void;
}

/** One swap ring, from the point of view of the student looking at it.
 *
 * Rings overlap on purpose, so three states have to be distinguishable:
 * offerable, already spent on another offer of your own, and taken by
 * someone else who got there first.
 */
export function ChainCard({ option, rank, myRollNo, blockedByOwnOffer, onOffer }: Props) {
  const taken = !option.available;
  const title = taken
    ? `No longer available · ${option.myTo}`
    : rank === 0
      ? `Best option for you · ${option.myTo}`
      : `Option ${rank + 1} · ${option.myTo}`;

  return (
    <article className={`chain${taken ? " taken" : rank === 0 ? " best" : ""}`}>
      <div className="chain-head">
        <span className="title">{title}</span>
        <span className="meta">
          {option.myMatch}% match for you · {option.members.length} students move together
        </span>
      </div>
      <div className="steps">
        {option.members.map((m) => {
          const isMe = m.rollNo === myRollNo;
          return (
            <div className="step" key={m.studentId}>
              <span className={isMe ? "who me" : "who"}>
                {m.name}
                {isMe ? " (you)" : ""}
              </span>
              <span className="move">
                {m.from}
                <span className="arrow">&rarr;</span>
                {m.to}
              </span>
              <span className="match">{m.match}%</span>
            </div>
          );
        })}
      </div>
      {taken ? (
        <p className="muted" style={{ margin: 0 }}>
          {option.takenBy.join(", ")} committed to another swap, so this ring can no longer run.
        </p>
      ) : blockedByOwnOffer ? (
        <p className="muted" style={{ margin: 0 }}>
          You already have an offer awaiting replies. Settle it before offering another ring.
        </p>
      ) : (
        <button className="btn btn-success btn-sm" type="button" onClick={() => onOffer(option)}>
          Offer this swap
        </button>
      )}
    </article>
  );
}
