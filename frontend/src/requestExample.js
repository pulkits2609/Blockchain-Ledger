export function exampleData(fields, includeOptional = false) {
  const data = {};
  for (const field of fields || []) {
    if (field.required === false && !includeOptional) continue;
    const values = { string: 'example', integer: 1, boolean: true, object: {}, array: [] };
    // defineProperty also handles legal field names such as __proto__ as ordinary JSON keys.
    Object.defineProperty(data, field.name, { value: values[field.type], enumerable: true, configurable: true });
  }
  return data;
}
