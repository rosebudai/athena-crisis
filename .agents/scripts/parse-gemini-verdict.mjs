#!/usr/bin/env node

import { readFileSync } from 'node:fs';
import process from 'node:process';

function extractFirstJSONObject(input) {
  let depth = 0;
  let start = -1;
  let inString = false;
  let escaping = false;

  for (let index = 0; index < input.length; index++) {
    const character = input[index];

    if (inString) {
      if (escaping) {
        escaping = false;
      } else if (character === '\\') {
        escaping = true;
      } else if (character === '"') {
        inString = false;
      }

      continue;
    }

    if (character === '"') {
      inString = true;
      continue;
    }

    if (character === '{') {
      if (depth === 0) {
        start = index;
      }
      depth++;
      continue;
    }

    if (character === '}') {
      if (depth === 0) {
        continue;
      }

      depth--;
      if (depth === 0 && start !== -1) {
        return input.slice(start, index + 1);
      }
    }
  }

  throw new Error('No top-level JSON object found in Gemini output.');
}

function normalizeVerdict(parsed, sourcePath) {
  if (!parsed || typeof parsed !== 'object' || Array.isArray(parsed)) {
    throw new Error('Parsed verdict is not a JSON object.');
  }

  if (typeof parsed.pass !== 'boolean') {
    throw new Error('Parsed verdict is missing required boolean field "pass".');
  }

  if (parsed.failures != null && !Array.isArray(parsed.failures)) {
    throw new Error('Parsed verdict field "failures" must be an array when present.');
  }

  return {
    ...parsed,
    failures: Array.isArray(parsed.failures)
      ? parsed.failures.map((failure) => String(failure))
      : [],
    parser: {
      extracted_json: true,
      source: sourcePath,
    },
  };
}

function main() {
  const [sourcePath] = process.argv.slice(2);
  if (!sourcePath) {
    throw new Error('Usage: node .agents/scripts/parse-gemini-verdict.mjs <raw-verdict-path>');
  }

  const raw = readFileSync(sourcePath, 'utf8');
  const jsonText = extractFirstJSONObject(raw);
  const parsed = JSON.parse(jsonText);
  const normalized = normalizeVerdict(parsed, sourcePath);
  process.stdout.write(`${JSON.stringify(normalized, null, 2)}\n`);
}

try {
  main();
} catch (error) {
  console.error(error instanceof Error ? error.message : String(error));
  process.exit(1);
}
