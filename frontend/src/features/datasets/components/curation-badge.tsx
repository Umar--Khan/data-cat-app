import { Database, Sparkles, Tag, TriangleAlert, type LucideIcon } from 'lucide-react'
import type { ComponentProps } from 'react'
import { Badge } from '@/components/ui/badge'
import type { Curation } from '@/lib/api/schema.gen'

interface CurationLabel {
  text: string
  icon: LucideIcon
  tone: ComponentProps<typeof Badge>['tone']
}

// Keyed by the generated unions, so a status or provider the API adds fails tsc until it has a label.
const failedLabel: CurationLabel = { text: 'Curation failed', icon: TriangleAlert, tone: 'warning' }

const completedLabels: Record<Curation['provider'], CurationLabel> = {
  anthropic: { text: 'Curated by Claude', icon: Sparkles, tone: 'accent' },
  keyword: { text: 'Keyword curated', icon: Tag, tone: 'neutral' },
  seed: { text: 'Sample data', icon: Database, tone: 'neutral' },
}

const labelFor: Record<Curation['status'], (curation: Curation) => CurationLabel> = {
  failed: () => failedLabel,
  completed: ({ provider }) => completedLabels[provider],
}

export function CurationBadge({ curation }: { curation: Curation }) {
  const { text, icon, tone } = labelFor[curation.status](curation)
  return (
    <Badge tone={tone} icon={icon}>
      {text}
    </Badge>
  )
}
