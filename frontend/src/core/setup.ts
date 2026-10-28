/**
 * What the Host may set up for a game, read from the protocol the server validates with:
 * which numbers are bounded and how, and the defaults. The server stays the authority: it
 * also checks what the protocol cannot say, such as the Murderers being at most a quarter
 * of the town.
 */
import protocol from "../../../protocol/murdertown.schema.json";
import type { GameConfigInput } from "../protocol";

interface Property {
  type?: string;
  minimum?: number;
  maximum?: number;
  anyOf?: Property[];
  default?: unknown;
}

const properties: Record<string, Property> = protocol.$defs["GameConfig-Input"].properties;

type NumbersOf<T> = { [K in keyof T]-?: NonNullable<T[K]> extends number ? K : never }[keyof T];

/** The numbers the Host sets, but the seed: it has no bounds, and the server draws one left out. */
export type NumberField = Exclude<NumbersOf<GameConfigInput>, "seed">;

/** A property's number, when it may also be left empty (null). */
function numberIn(property: Property): Property {
  return property.anyOf?.find((option) => option.type !== "null") ?? property;
}

/** Every number the protocol bounds, so a new one is checked without a change here. */
const BOUNDED = Object.keys(properties).filter((field) => {
  const property = properties[field];
  return property !== undefined && numberIn(property).minimum !== undefined;
}) as NumberField[];

export interface Bounds {
  min: number;
  max: number;
  whole: boolean;
  /** Whether it may be left empty (null), as the Open floor's time limit may. */
  optional: boolean;
}

export function boundsOf(field: NumberField): Bounds {
  const property = properties[field];
  const number = property && numberIn(property);
  if (number?.minimum === undefined || number.maximum === undefined) {
    throw new Error(`The protocol does not bound ${field}`);
  }
  return {
    min: number.minimum,
    max: number.maximum,
    whole: number.type === "integer",
    optional: property?.anyOf?.some((option) => option.type === "null") ?? false,
  };
}

/** The server's defaults for every choice that has one; the seed has none. */
export function defaultConfig(): GameConfigInput {
  const defaults = Object.entries(properties)
    .filter(([, property]) => "default" in property)
    .map(([field, property]) => [field, structuredClone(property.default)]);
  return Object.fromEntries(defaults) as GameConfigInput;
}

/** What is wrong with each number out of bounds, by field. */
export function problemsWith(config: GameConfigInput): Partial<Record<NumberField, string>> {
  const problems: Partial<Record<NumberField, string>> = {};
  for (const field of BOUNDED) {
    const value = config[field];
    const { min, max, whole, optional } = boundsOf(field);
    if (value === undefined || (value === null && optional)) continue;
    if (value === null || !Number.isFinite(value)) problems[field] = "a number";
    else if (whole && !Number.isInteger(value)) problems[field] = "a whole number";
    else if (value < min) problems[field] = `at least ${min}`;
    else if (value > max) problems[field] = `at most ${max}`;
  }
  return problems;
}
