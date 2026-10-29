import { type FormEvent, type ReactNode, useEffect, useState } from "react";

import { boundsOf, defaultConfig, type NumberField, problemsWith } from "../core/setup";
import { failure } from "../net/fetchJson";
import type { Estimator } from "../net/games";
import type { Estimate, GameConfigInput, LineupInput, PlayedByInput, SetupChoices, Side } from "../protocol";
import { aboutDollars, numberLabel, sheriffFiresLabel, sideLabel } from "./labels";
import { PlayedByFields } from "./PlayedByFields";
import { fieldStyle, inputStyle } from "./styles";

const DEFAULTS = defaultConfig();

/** How long the setup must stay unchanged before its Expected cost is asked for again. */
export const ESTIMATE_AFTER_MS = 300;

const SIDES: readonly { side: Side; label: string }[] = [
  { side: "murderers", label: "The Murderers play differently" },
  { side: "town", label: "The Town plays differently" },
];

interface SeatChoice {
  seat: number;
  playedBy: PlayedByInput;
}

/**
 * The Host's setup form: the town, its rules, the seed and who plays each Resident.
 * Numbers are bounded as the protocol says and checked before a game is started; the
 * server stays the authority, and its reasons for refusing are shown as they come.
 * A seed left empty is drawn by the server: a known seed would tell every role. Below the
 * form, the server's estimate of what the setup would cost, asked for again once the setup
 * settles, and never while it has a problem.
 */
export function SetupForm({
  choices,
  onStart,
  estimate,
}: {
  choices: SetupChoices | null;
  onStart: (config: GameConfigInput) => Promise<void>;
  estimate: Estimator;
}) {
  const [config, setConfig] = useState<GameConfigInput>(() => structuredClone(DEFAULTS));
  const [seed, setSeed] = useState("");
  const [refusal, setRefusal] = useState<string | null>(null);
  const [cost, setCost] = useState<Priced | null>(null);

  const change = (update: Partial<GameConfigInput>) => setConfig((now) => ({ ...now, ...update }));
  const lineup: LineupInput = config.lineup ?? {};
  const changeLineup = (update: Partial<LineupInput>) => change({ lineup: { ...lineup, ...update } });
  const everyone: PlayedByInput = lineup.everyone ?? {};
  const seats: SeatChoice[] = Object.entries(lineup.seats ?? {}).map(([seat, playedBy]) => ({
    seat: Number(seat),
    playedBy,
  }));
  const changeSeats = (changed: SeatChoice[]) =>
    changeLineup({ seats: Object.fromEntries(changed.map(({ seat, playedBy }) => [String(seat), playedBy])) });
  const replaceSeat = (index: number, replacement: SeatChoice) =>
    changeSeats(seats.map((choice, i) => (i === index ? replacement : choice)));
  const seatNumbers = [...Array(config.residents ?? 0).keys()];
  const taken = (seat: number) => seats.some((choice) => choice.seat === seat);

  const problems: string[] = Object.entries(problemsWith(config)).map(
    ([name, problem]) => `${numberLabel[name as NumberField]}: ${problem}`,
  );
  if (seed.trim() !== "" && !Number.isInteger(Number(seed))) problems.push("Seed: a whole number");
  const chosen = seed.trim() === "" ? {} : { seed: Number(seed) };
  // the setup to price, as text so that the effect sees a change in its contents, not a new object
  const setup = JSON.stringify(problems.length > 0 ? null : { ...config, ...chosen });

  useEffect(() => {
    const priced = JSON.parse(setup) as GameConfigInput | null;
    if (priced === null) return;
    let current = true; // a slower answer to an older setup must not replace a newer one
    const timer = setTimeout(() => {
      estimate(priced).then(
        (expected) => current && setCost({ setup, expected }),
        (error: unknown) => current && setCost({ setup, refused: failure(error) }),
      );
    }, ESTIMATE_AFTER_MS);
    return () => {
      current = false;
      clearTimeout(timer);
    };
  }, [setup, estimate]);

  const submit = (event: FormEvent) => {
    event.preventDefault();
    if (problems.length > 0) return;
    setRefusal(null);
    onStart({ ...config, ...chosen }).catch((error: unknown) =>
      setRefusal(failure(error)),
    );
  };

  const number = (name: NumberField) => (
    <NumberInput name={name} value={config[name]} onChange={(value) => change({ [name]: value })} />
  );
  const toggle = (name: "doctor" | "detective" | "sheriff" | "dawn_names_the_saved", label: string) => (
    <label className="flex items-center gap-2 text-sm">
      <input type="checkbox" checked={config[name] ?? false} onChange={(event) => change({ [name]: event.target.checked })} />
      {label}
    </label>
  );

  return (
    <form onSubmit={submit} className="flex flex-col gap-6">
      <Section title="The town">
        {number("residents")}
        {number("murderers")}
        <div className="flex flex-col gap-1">
          {toggle("doctor", "Doctor")}
          {toggle("detective", "Detective")}
          {toggle("sheriff", "Sheriff")}
        </div>
      </Section>

      <Section title="The rules">
        {number("max_days")}
        {number("open_floor_statements")}
        <div className="flex flex-col gap-1">
          {number("open_floor_seconds")}
          <label className="flex items-center gap-2 text-sm">
            <input
              type="checkbox"
              checked={config.open_floor_seconds === null}
              onChange={(event) => change({ open_floor_seconds: event.target.checked ? null : (DEFAULTS.open_floor_seconds ?? null) })}
            />
            No time limit
          </label>
        </div>
        {number("detective_accuracy")}
        <label className={fieldStyle}>
          <span>The Sheriff fires</span>
          <select
            className={inputStyle}
            value={config.sheriff_shoots_at}
            onChange={(event) => change({ sheriff_shoots_at: event.target.value as keyof typeof sheriffFiresLabel })}
          >
            {Object.entries(sheriffFiresLabel).map(([when, label]) => (
              <option key={when} value={when}>
                {label}
              </option>
            ))}
          </select>
        </label>
        {toggle("dawn_names_the_saved", "Dawn names whom the Doctor saved")}
      </Section>

      <Section title="Who plays">
        <div className="flex w-full flex-col gap-3">
          <PlayedByFields legend="Everyone" value={everyone} choices={choices} onChange={(value) => changeLineup({ everyone: value })} />
          {SIDES.map(({ side, label }) => {
            const own = lineup[side];
            return (
              <div key={side} className="flex flex-col gap-2">
                <label className="flex items-center gap-2 text-sm">
                  <input
                    type="checkbox"
                    checked={Boolean(own)}
                    onChange={(event) => changeLineup({ [side]: event.target.checked ? { ...everyone } : null })}
                  />
                  {label}
                </label>
                {own && (
                  <PlayedByFields
                    legend={sideLabel[side]}
                    value={own}
                    choices={choices}
                    onChange={(value) => changeLineup({ [side]: value })}
                  />
                )}
              </div>
            );
          })}
          {seats.map(({ seat, playedBy }, index) => (
            <PlayedByFields
              key={index}
              legend="One seat"
              value={playedBy}
              choices={choices}
              onChange={(value) => replaceSeat(index, { seat, playedBy: value })}
            >
              <label className={fieldStyle}>
                <span>Seat</span>
                <select
                  className={inputStyle}
                  value={seat}
                  onChange={(event) => replaceSeat(index, { seat: Number(event.target.value), playedBy })}
                >
                  {seatNumbers
                    .filter((option) => option === seat || !taken(option))
                    .map((option) => (
                      <option key={option}>{option}</option>
                    ))}
                </select>
              </label>
              <button
                type="button"
                className="text-sm text-stone-400 hover:text-rose-300"
                onClick={() => changeSeats(seats.filter((_, i) => i !== index))}
              >
                Remove
              </button>
            </PlayedByFields>
          ))}
          <button
            type="button"
            className="self-start text-sm text-amber-200 hover:underline"
            onClick={() => {
              const seat = seatNumbers.find((option) => !taken(option));
              if (seat !== undefined) changeSeats([...seats, { seat, playedBy: { ...everyone } }]);
            }}
          >
            Add a seat
          </button>
        </div>
      </Section>

      <Section title="The seed">
        <label className={fieldStyle}>
          <span>Seed</span>
          <input
            type="text"
            inputMode="numeric"
            className={inputStyle}
            placeholder="drawn at random"
            value={seed}
            onChange={(event) => setSeed(event.target.value)}
          />
        </label>
        <p className="max-w-md text-sm text-stone-400">
          The same seed and the same decisions make the same game. Leave it empty: anyone who knows the seed can work out
          every role.
        </p>
      </Section>

      {problems.length > 0 && (
        <ul aria-label="Problems" className="text-sm text-rose-300">
          {problems.map((problem) => (
            <li key={problem}>{problem}</li>
          ))}
        </ul>
      )}
      {cost?.setup === setup && <ExpectedCost cost={cost} />}
      {refusal && (
        <p role="alert" className="text-sm text-rose-300">
          {refusal}
        </p>
      )}
      <button type="submit" className="self-start rounded bg-amber-300 px-4 py-2 font-semibold text-stone-950 hover:bg-amber-200">
        Start the game
      </button>
    </form>
  );
}

/** The setup's expected equivalent cost, with each model's share. */
/** The Expected cost of a setup, or why the server could not work it out. */
type Priced = { setup: string } & ({ expected: Estimate } | { refused: string });

/** The setup's Expected cost, with each model's share, or the server's reason for none. */
function ExpectedCost({ cost }: { cost: Priced }) {
  return (
    <p role="status" aria-label="Expected cost" className="max-w-xl text-sm text-stone-300">
      {"refused" in cost ? `No estimate: ${cost.refused}` : describe(cost.expected)}
    </p>
  );
}

function describe({ usd, by_model, days }: Estimate): string {
  const shares = Object.entries(by_model).map(([model, share]) => `${model} ${aboutDollars(share)}`);
  if (shares.length === 0) return "Costs nothing: every Resident is scripted.";
  return (
    `About ${aboutDollars(usd)} equivalent for a game of ${days} Days: ${shares.join(" · ")}. ` +
    "On your Claude subscription that costs nothing extra but uses its quota; on an API key it is about what you pay."
  );
}

function Section({ title, children }: { title: string; children: ReactNode }) {
  return (
    <section className="flex flex-col gap-3">
      <h2 className="font-serif text-xl text-amber-200">{title}</h2>
      <div className="flex flex-wrap items-start gap-6">{children}</div>
    </section>
  );
}

function NumberInput({
  name,
  value,
  onChange,
}: {
  name: NumberField;
  value: number | null | undefined;
  onChange: (value: number) => void;
}) {
  const { min, max, whole } = boundsOf(name);
  return (
    <label className={fieldStyle}>
      <span>{numberLabel[name]}</span>
      <input
        type="number"
        className={inputStyle}
        min={min}
        max={max}
        step={whole ? 1 : "any"}
        disabled={value === null}
        value={value ?? ""}
        onChange={(event) => onChange(event.target.value === "" ? Number.NaN : Number(event.target.value))}
      />
    </label>
  );
}
