import { expect, press, seedNames, tabTo, test, testPayload, toast } from './fixtures.ts'

// Navigation and activation use only Tab, Shift+Tab, Enter, Space and Esc, each press followed by a
// check that focus did not fall to the body.

test('adds and deletes a dataset with the keyboard alone', async ({ page }) => {
  await page.goto('/')
  await expect(page.getByRole('heading', { level: 3 })).toHaveText(seedNames)

  const name = page.getByRole('textbox', { name: 'Name', exact: true })
  const deleteButton = page.getByRole('button', { name: `Delete ${testPayload.name}`, exact: true })
  const dialog = page.getByRole('alertdialog', { name: `Delete "${testPayload.name}"?` })
  const cancel = dialog.getByRole('button', { name: 'Cancel', exact: true })
  const confirm = dialog.getByRole('button', { name: 'Delete dataset', exact: true })

  await test.step('add', async () => {
    await tabTo(page, name)
    await page.keyboard.type(testPayload.name)
    await tabTo(page, page.getByRole('textbox', { name: 'Owner', exact: true }))
    await page.keyboard.type(testPayload.owner)
    await tabTo(page, page.getByRole('textbox', { name: 'Description', exact: true }))
    await page.keyboard.type(testPayload.description)
    await tabTo(page, page.getByRole('button', { name: 'Add dataset', exact: true }))
    await press(page, 'Enter')

    await expect(toast(page, `Added "${testPayload.name}"`)).toBeVisible()
    await expect(page.getByRole('heading', { level: 3 })).toHaveText([
      ...seedNames,
      testPayload.name,
    ])
    await expect(name).toBeFocused()
  })

  await test.step('open the dialog, move within it, and dismiss it with Esc', async () => {
    await tabTo(page, deleteButton)
    await press(page, 'Enter')
    await expect(dialog).toBeVisible()
    await expect(cancel).toBeFocused()
    await press(page, 'Tab')
    await expect(confirm).toBeFocused()
    await press(page, 'Shift+Tab')
    await expect(cancel).toBeFocused()

    await press(page, 'Escape')
    await expect(dialog).toBeHidden()
    await expect(deleteButton).toBeFocused()
  })

  await test.step('delete', async () => {
    await press(page, 'Space')
    await expect(cancel).toBeFocused()
    await tabTo(page, confirm)
    await press(page, 'Enter')

    await expect(toast(page, `Deleted "${testPayload.name}"`)).toBeVisible()
    await expect(page.getByRole('heading', { level: 3 })).toHaveText(seedNames)
    // The deleted row was last, so focus moves to the previous row's heading.
    await expect(
      page.getByRole('heading', { name: 'Employee Directory', exact: true }),
    ).toBeFocused()
  })
})
