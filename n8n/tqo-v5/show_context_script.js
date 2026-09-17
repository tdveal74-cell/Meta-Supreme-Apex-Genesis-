const nco = $json.nco === true;
return [{ json: nco ? {
  show: 'NCO', channel: 'NCO Forge', tableId: 'nco_content', tableRef: 'DSH1tn4TZjzAEKxp',
  brand: 'nco', kicker: 'NCO FORGE',
  // Brand hierarchy from the Aug 2026 audit: brand, then emotion, then position.
  tagline: "Leaders aren't born. They're forged.",
  positioning: 'Where doctrine ends and leadership begins.',
  tagline2: 'Built by Discipline. Living on Purpose.',
  thesis: 'NCO Forge is where military experience becomes leadership judgment. The situations nobody can teach you from a slide.',
  requiredTags: ['NCO Forge'],
  scriptLimit: 2, promoteLimit: 1,
} : {
  show: 'TQO', channel: 'The Quiet Operator', tableId: 'tqo_content', tableRef: '2GtmrFcTNqVMbddh',
  brand: 'tqo', kicker: 'THE QUIET OPERATOR',
  tagline: 'AI Strategy for the Next Economy.',
  positioning: 'Leverage for the people the AI economy is quietly repricing.',
  tagline2: 'Quiet Leverage. Real Results.',
  thesis: 'The Quiet Operator is where professional judgment survives automation. Receipts, not predictions.',
  requiredTags: [],
  scriptLimit: 2, promoteLimit: 1,
} }];