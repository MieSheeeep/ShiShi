import { reactive } from 'vue'
import { api } from './recipeEditing.js'
import { createJournal } from './cookingJournal.js'
export function useCookingJournal() { return createJournal(api,reactive) }
