import { zodResolver } from '@hookform/resolvers/zod'
import { useRef, useState } from 'react'
import { useForm } from 'react-hook-form'
import { Alert } from '@/components/ui/alert'
import { Button } from '@/components/ui/button'
import { TextareaField, TextField } from '@/components/ui/field'
import { useCreateDataset } from '@/features/datasets/hooks/use-datasets'
import { ApiError } from '@/lib/api/api-error'
import type { DatasetCreate } from '@/lib/api/schema.gen'
import { applyServerErrors } from '@/lib/forms/apply-server-errors'
import { datasetFormSchema } from './dataset-form-schema'

const fields = ['name', 'owner', 'description'] as const

const descriptionHint =
  'What the data contains and how often it updates. Used to generate tags and a summary.'

// Mirrors the default of CATALOGUE_ANTHROPIC_TIMEOUT_SECONDS on the backend.
const pendingMessage = 'Generating tags and a summary. This can take up to 20 seconds.'

export function DatasetForm() {
  const { mutate, isPending } = useCreateDataset()
  const [submitError, setSubmitError] = useState<string>()
  const formRef = useRef<HTMLFormElement>(null)
  const {
    register,
    handleSubmit,
    reset,
    setError,
    setFocus,
    formState: { errors },
  } = useForm({
    resolver: zodResolver(datasetFormSchema),
    defaultValues: { name: '', owner: '', description: '' },
  })

  // mutate returns at once, so handleSubmit settles before the response arrives. Resetting in the
  // mutation's callback therefore also clears the submitted state handleSubmit sets, and the next
  // entry validates on submit again rather than on every keystroke.
  function create(values: DatasetCreate) {
    mutate(values, {
      onSuccess: () => {
        // setFocus looks the input up among the registered fields, which a plain reset empties
        // until the next render registers them again.
        reset(undefined, { keepFieldsRef: true })
        // Curation can take 20 seconds, long enough to move on to the list, and a focus jump then
        // would send the next key press to the form. Focus on the body counts as still in the
        // form: Safari leaves it there after a click on the submit button.
        const focused = document.activeElement
        if (focused === document.body || formRef.current?.contains(focused)) setFocus('name')
      },
      onError: (error) => {
        if (!(error instanceof ApiError && applyServerErrors(error, setError, fields))) {
          setSubmitError(error.message)
        }
      },
    })
  }

  return (
    <form
      ref={formRef}
      noValidate
      onSubmit={(event) => {
        // Cleared on every attempt, so a repeated failure mounts the alert again and is announced.
        setSubmitError(undefined)
        void handleSubmit(create)(event)
      }}
      className="flex flex-col gap-5 rounded-lg border border-border bg-surface p-5 shadow-sm sm:p-6"
    >
      <p className="text-sm text-fg-muted">All fields are required.</p>
      <TextField
        label="Name"
        required
        autoComplete="off"
        readOnly={isPending}
        error={errors.name?.message}
        {...register('name')}
      />
      <TextField
        label="Owner"
        required
        autoComplete="off"
        readOnly={isPending}
        error={errors.owner?.message}
        {...register('owner')}
      />
      <TextareaField
        label="Description"
        hint={descriptionHint}
        rows={4}
        required
        readOnly={isPending}
        error={errors.description?.message}
        {...register('description')}
      />
      {submitError && (
        <Alert tone="danger" role="alert" title="Couldn't add the dataset">
          {submitError}
        </Alert>
      )}
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2">
        <Button type="submit" pending={isPending}>
          {isPending ? 'Saving and curating…' : 'Add dataset'}
        </Button>
        <p role="status" className="text-sm text-fg-muted">
          {isPending && pendingMessage}
        </p>
      </div>
    </form>
  )
}
