/**
 * Nature translation utilities for multi-language support.
 * 
 * The database always stores English nature names. This module provides
 * display-layer translation for French users.
 */

// English → French nature name mapping (all 25 Pokémon natures)
const ENGLISH_TO_FRENCH = {
  Hardy:    'Hardi',
  Lonely:   'Solo',
  Brave:    'Brave',
  Adamant:  'Rigide',
  Naughty:  'Mauvais',
  Bold:     'Assuré',
  Docile:   'Docile',
  Relaxed:  'Relax',
  Impish:   'Malin',
  Lax:      'Lâche',
  Timid:    'Timide',
  Hasty:    'Pressé',
  Serious:  'Sérieux',
  Jolly:    'Jovial',
  Naive:    'Naïf',
  Modest:   'Modeste',
  Mild:     'Doux',
  Quiet:    'Discret',
  Bashful:  'Pudique',
  Rash:     'Foufou',
  Calm:     'Calme',
  Gentle:   'Gentil',
  Sassy:    'Malpoli',
  Careful:  'Prudent',
  Quirky:   'Bizarre',
}

/**
 * Translate an English nature name for display.
 * 
 * @param {string} englishName - English nature name (e.g., 'Adamant')
 * @param {string} language - Game language ('en' or 'fr')
 * @returns {string} Translated nature name, or the original if no translation exists
 */
export function displayNature(englishName, language) {
  if (!englishName || language !== 'fr') return englishName
  return ENGLISH_TO_FRENCH[englishName] || englishName
}

/**
 * Translate a nature dict's keys for chart display.
 * Converts { 'Adamant': 5, 'Jolly': 3 } → [{ name: 'Rigide', count: 5 }, ...]
 * 
 * @param {Object} naturesDict - { englishName: count } from the API
 * @param {string} language - Game language ('en' or 'fr')
 * @returns {Array} Array of { name, count } with translated names
 */
export function translateNatureDict(naturesDict, language) {
  return Object.entries(naturesDict || {}).map(([name, count]) => ({
    name: displayNature(name, language),
    englishName: name,
    count,
  }))
}

export { ENGLISH_TO_FRENCH }
