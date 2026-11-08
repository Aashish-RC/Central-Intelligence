/**
 * DataValue Contract
 * Sourced from Rivet (packages/core/src/model/DataValue.ts) - MIT License
 *
 * Defines runtime typed data representations passed between nodes in the graph canvas.
 */

export type DataValueDef<Type extends string, RuntimeType> = {
  type: Type;
  value: RuntimeType;
};

export type StringDataValue = DataValueDef<'string', string>;
export type NumberDataValue = DataValueDef<'number', number>;
export type BoolDataValue = DataValueDef<'boolean', boolean>;

export type ChatMessage = {
  type: 'system' | 'user' | 'assistant' | 'function';
  message: string | unknown;
  name?: string;
  function_call?: { id?: string; name: string; arguments: string };
};

export type ChatMessageDataValue = DataValueDef<'chat-message', ChatMessage>;
export type DateDataValue = DataValueDef<'date', string>;
export type TimeDataValue = DataValueDef<'time', string>;
export type DateTimeDataValue = DataValueDef<'datetime', string>;
export type AnyDataValue = DataValueDef<'any', unknown>;
export type ObjectDataValue = DataValueDef<'object', Record<string, unknown>>;
export type ArrayDataValue = DataValueDef<'array', unknown[]>;
export type VectorDataValue = DataValueDef<'vector', number[]>;
export type BinaryDataValue = DataValueDef<'binary', Uint8Array>;
export type ImageDataValue = DataValueDef<'image', { mediaType: string; data: Uint8Array }>;
export type AudioDataValue = DataValueDef<'audio', { mediaType?: string; data: Uint8Array }>;

export type DataValue =
  | StringDataValue
  | NumberDataValue
  | BoolDataValue
  | ChatMessageDataValue
  | DateDataValue
  | TimeDataValue
  | DateTimeDataValue
  | AnyDataValue
  | ObjectDataValue
  | ArrayDataValue
  | VectorDataValue
  | BinaryDataValue
  | ImageDataValue
  | AudioDataValue;

export function coerceToString(value: DataValue | unknown): string {
  if (value === null || value === undefined) return '';
  if (typeof value === 'object' && 'type' in (value as any) && 'value' in (value as any)) {
    const dv = value as DataValue;
    if (dv.type === 'string') return dv.value;
    if (typeof dv.value === 'object') return JSON.stringify(dv.value);
    return String(dv.value);
  }
  if (typeof value === 'object') return JSON.stringify(value);
  return String(value);
}
