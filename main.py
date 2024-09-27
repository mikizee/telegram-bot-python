import logging
from typing import Final
from telegram import Update, InputFile, ReplyKeyboardMarkup, KeyboardButton
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, ConversationHandler
import os

# Replace with your actual bot token
TOKEN: Final = '8129607847:AAGdnV56nUbNbWofckGOD-HvW-b3le5h6pY'

# Admin user ID (your Telegram user ID)
ADMIN_USER_ID: Final = 946800596  # Your actual user ID

# Define states
FIN, NAME, PDF, SCREENSHOT, FEEDBACK, USER_ID, REASON, FEEDBACK_FIN = range(8)

# Dictionary to store user data
user_data = {}

# Enable logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.DEBUG  # Set to DEBUG for more detailed logging
)
logger = logging.getLogger(__name__)  # Correct logger name

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Please enter your 12-digit FIN number:')
    return FIN

async def fin_number(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fin = update.message.text.strip()
    if len(fin) == 12 and fin.isdigit():
        formatted_fin = ' '.join([fin[i:i+4] for i in range(0, len(fin), 4)])
        context.user_data['fin'] = formatted_fin
        await update.message.reply_text(f'FIN accepted! Formatted: {formatted_fin}. Now please enter your full name:')
        return NAME
    else:
        await update.message.reply_text('Invalid FIN. Please enter a 12-digit FIN number:')
        return FIN

async def full_name(update: Update, context: ContextTypes.DEFAULT_TYPE):
    name = update.message.text.strip()
    context.user_data['name'] = name
    await update.message.reply_text('Full name accepted! You can now send a PDF file.')
    return PDF

async def handle_pdf(update: Update, context: ContextTypes.DEFAULT_TYPE):
    document = update.message.document

    if document and document.mime_type == 'application/pdf':
        file_id = document.file_id
        file_path = os.path.join('downloads', document.file_name)

        try:
            file = await context.bot.get_file(file_id)
            await file.download_to_drive(file_path)

            await update.message.reply_text(f"Received your PDF file: {document.file_name}")

            user_id = update.message.from_user.id
            user_data[user_id] = {
                'file_path': file_path,
                'fin': context.user_data['fin'],
                'name': context.user_data['name'],
                'user_id': user_id
            }

            # Notify user to send payment screenshot
            await update.message.reply_text(
                "Pay 200 birr on Telebirr using 0925061615 and send the screenshot! Please upload the screenshot here."
            )
            return SCREENSHOT
        except Exception as e:
            logger.error(f"Error handling PDF: {e}")
            await update.message.reply_text("Error handling your PDF. Please try again.")
    else:
        await update.message.reply_text("Please send a valid PDF file.")

    return ConversationHandler.END

async def handle_screenshot(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.photo:
        screenshot = update.message.photo[-1]  # Get the highest resolution screenshot
        screenshot_file_id = screenshot.file_id

        user_id = update.message.from_user.id
        fin = user_data[user_id]['fin']
        name = user_data[user_id]['name']

        try:
            # Notify admin about the screenshot and send the PDF and screenshot together
            await context.bot.send_document(chat_id=ADMIN_USER_ID, document=user_data[user_id]['file_path'],
                                            caption=f"Received PDF and payment from user:\nFIN: {fin}\nName: {name}\nUser ID: {user_id}")

            await context.bot.send_photo(chat_id=ADMIN_USER_ID, photo=screenshot_file_id,
                                         caption=f"Payment screenshot for user:\nFIN: {fin}\nName: {name}")
            await update.message.reply_text("Your request is submitted for approval.")
            return ConversationHandler.END

        except Exception as e:
            logger.error(f"Error sending screenshot to admin: {e}")
            await update.message.reply_text("Error sending your payment screenshot. Please try again.")
    else:
        await update.message.reply_text("Please send a screenshot of your payment.")
        return SCREENSHOT

async def feedback_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.message.from_user.id

    # Check if the current user is the admin
    if user_id == ADMIN_USER_ID:
        await update.message.reply_text("Please enter the user ID to provide feedback for:")
        return USER_ID
    else:
        await update.message.reply_text("You are not authorized to use this command.")
        return ConversationHandler.END

async def handle_user_id_for_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        user_id = int(update.message.text.strip())

        # Check if the user ID exists in the user_data
        if user_id in user_data:
            context.user_data['current_user_id'] = user_id
            await update.message.reply_text("User found! Now please provide the FIN number:")
            return FEEDBACK_FIN
        else:
            await update.message.reply_text("No user found with that ID. Please try again.")
            return USER_ID
    except ValueError:
        await update.message.reply_text("Invalid user ID format. Please enter a numeric user ID.")
        return USER_ID

async def handle_feedback_fin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    fin = update.message.text.strip()
    # You can validate the FIN number if needed here
    context.user_data['feedback_fin'] = fin
    
    # Prompt for feedback choice
    await update.message.reply_text("Now provide feedback by choosing:")
    
    # Create buttons for accept and decline
    keyboard = [[KeyboardButton("Accept"), KeyboardButton("Decline")]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("Choose an option:", reply_markup=reply_markup)

    return FEEDBACK

async def handle_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = context.user_data['current_user_id']
    choice = update.message.text.strip().lower()

    if choice == "accept":
        feedback_fin = context.user_data['feedback_fin']
        await context.bot.send_message(chat_id=user_id, text=f"Your request has been accepted. FIN: {feedback_fin}")
        await update.message.reply_text("Feedback sent to the user.")
        return ConversationHandler.END
    elif choice == "decline":
        await update.message.reply_text("Please provide a reason for declining:")
        return REASON
    else:
        await update.message.reply_text("Invalid choice. Please choose either 'Accept' or 'Decline'.")
        return FEEDBACK

async def handle_decline_reason(update: Update, context: ContextTypes.DEFAULT_TYPE):
    reason = update.message.text.strip()
    user_id = context.user_data['current_user_id']

    # Send the decline reason back to the user
    await context.bot.send_message(chat_id=user_id, text=f"Your request was declined. Reason: {reason}")
    await update.message.reply_text("Decline reason sent to the user.")
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text('Operation cancelled.')
    return ConversationHandler.END

def main():
    app = Application.builder().token(TOKEN).build()

    # Define conversation handler for user registration (FIN, NAME, PDF)
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start_command)],
        states={
            FIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, fin_number)],
            NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, full_name)],
            PDF: [MessageHandler(filters.Document.PDF, handle_pdf)],
            SCREENSHOT: [MessageHandler(filters.PHOTO, handle_screenshot)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Define conversation handler for feedback (USER_ID, FIN, FEEDBACK)
    feedback_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('feedback', feedback_command)],
        states={
            USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_user_id_for_feedback)],
            FEEDBACK_FIN: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback_fin)],
            FEEDBACK: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_feedback)],
            REASON: [MessageHandler(filters.TEXT & ~filters.COMMAND, handle_decline_reason)]
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    # Add conversation handler for registration flow
    app.add_handler(conv_handler)

    # Add conversation handler for feedback flow
    app.add_handler(feedback_conv_handler)

    logger.info("Bot is starting and ready to accept FIN, Name, PDF files, screenshots, and feedback...")

    # Start polling with logging enabled
    try:
        app.run_polling(poll_interval=5)
    except Exception as e:
        logger.error(f"Error during bot polling: {e}")

if __name__ == '__main__':
    main()
