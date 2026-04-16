import type { AbilityInfo, AbilityPresentation } from '../types/api';

function readPresentation(ability: AbilityInfo | null | undefined): AbilityPresentation | null {
  if (!ability?.presentation || typeof ability.presentation !== 'object') return null;
  return ability.presentation;
}

export function getAbilityPresentationName(ability: AbilityInfo | null | undefined) {
  const name = readPresentation(ability)?.name;
  return typeof name === 'string' && name.trim() ? name.trim() : null;
}

export function getAbilityPresentationSummary(ability: AbilityInfo | null | undefined) {
  const summary = readPresentation(ability)?.summary;
  return typeof summary === 'string' && summary.trim() ? summary.trim() : null;
}

export function getAbilityFormIntro(ability: AbilityInfo | null | undefined) {
  const formIntro = readPresentation(ability)?.formIntro;
  return typeof formIntro === 'string' && formIntro.trim() ? formIntro.trim() : null;
}

export function getAbilityExpectedOutput(ability: AbilityInfo | null | undefined) {
  const expectedOutput = readPresentation(ability)?.expectedOutput;
  return typeof expectedOutput === 'string' && expectedOutput.trim() ? expectedOutput.trim() : null;
}
