import logging
import os
import time
from datetime import datetime, timezone
import argparse
from collections import OrderedDict

from waggle.plugin import Plugin
from waggle.data.vision import Camera
from croniter import croniter


#takes in a task prompt and image, returns an answer 
def run_example(model, processor, task_prompt, image, text_input=None):
    if text_input is None:
        prompt = task_prompt
    else:
        prompt = task_prompt + text_input
    inputs = processor(text=prompt, images=image, return_tensors="pt")

    image_height, image_width = image.shape[:2]

    generated_ids = model.generate(
    input_ids=inputs["input_ids"],
    pixel_values=inputs["pixel_values"],
    #Changed from 1024 to 512
    max_new_tokens=512,
    #Changed from False to True
    early_stopping=False,
    do_sample=False,
    #changed from 3 to 2
    num_beams=2,
    )
    generated_text = processor.batch_decode(generated_ids, skip_special_tokens=False)[0]

    parsed_answer = processor.post_process_generation(
        generated_text, 
        task=task_prompt, 
        image_size=(image_width, image_height)
    )

    return parsed_answer

#takes in an image (img), returns a description (string)
def generateDescription(model, processor, image):
    task_prompt = '<MORE_DETAILED_CAPTION>'

    description_text = run_example(model, processor, task_prompt, image)
    description_text = description_text[task_prompt]

    #takes those details from the setences and finds labels and boxes in the image
    task_prompt = '<CAPTION_TO_PHRASE_GROUNDING>'
    boxed_descriptions = run_example(model, processor, task_prompt, image, description_text)

    #only prints out labels not bboxes
    descriptions = boxed_descriptions[task_prompt]['labels']
    logging.info(descriptions)


    #finds other things in the image that the description did not explicitly say
    task_prompt = '<DENSE_REGION_CAPTION>'
    labels = run_example(model, processor, task_prompt, image)

    #only prints out labels not bboxes
    printed_labels = labels[task_prompt]['labels']

    # Join description_text into a single string
    description_text_joined = "".join(description_text)

    #makes unique list of labels and adds commas
    label_list = descriptions + printed_labels
    unique_labels = list(OrderedDict.fromkeys(label_list))
    labels = ", ".join(unique_labels)

    # Combine all lists into one list
    combined_list = ["DESCRIPTION:"] + [description_text_joined] + ["LABELS:"] + [labels]

    # Join the unique items into a single string with spaces between them
    final_description = " ".join(combined_list)

    logging.info(final_description)
    return final_description


def captioning(args, model, processor, sample):
    if args.out_dir == "":
        description = generateDescription(model, processor, sample.data)
        logging.info(f'Description: {description}')
        sample_path = "sample.jpg"
        with Plugin() as plugin:
            if args.skip_uploading_image:
                logging.info("--skip-uploading-image is enabled. Skipping image upload.")
            else:
                sample.save(sample_path)
                plugin.upload_file(sample_path, timestamp=sample.timestamp)
                logging.info("Image staged for upload")
            plugin.publish("env.image.description", description, timestamp=sample.timestamp)
            logging.info("Published the description")
    else:
        dt = datetime.fromtimestamp(sample.timestamp / 1e9)
        base_dir = os.path.join(args.out_dir, dt.astimezone(timezone.utc).strftime('%Y/%m/%d/%H'))
        os.makedirs(base_dir, exist_ok=True)
        timeName = dt.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%S%z')
        sample_path = os.path.join(base_dir, f'{timeName}.jpg')
        text_path = os.path.join(base_dir, f'{timeName}.txt')
        description = generateDescription(model, processor, sample.data)
        logging.info(f'Description: {description}')

        sample.save(sample_path)
        with open(text_path, "w") as text_file:
            text_file.write(description)
        logging.info(f'Saved image: {sample_path}')
        logging.info(f'Saved description: {text_path}')


def get_input(stream):
    with Camera(stream) as cam:
        return cam.snapshot()


def run(args):
    if args.out_dir != "":
        logging.debug(f'Creating local directory: {args.out_dir}')
        os.makedirs(args.out_dir, exist_ok=True)

    if args.cronjob == "":
        logging.info("Run mode: one shot")
    else:
        logging.info(f'Run mode: cronjob: {args.cronjob}')
        if not croniter.is_valid(args.cronjob):
            logging.error(f'Cronjob format {args.cronjob} is not valid')
            return 1

    sample = None
    if args.fast_acquisition:
        logging.info(f'Fast input acquisition enabled. Taking an image before loading the model')
        sample = get_input(args.stream)
    
    logging.info(f'Loading the model from {args.model_path}')
    # We import the libraries here to avoid loading them at the beginning
    # because it take a while.
    from transformers import AutoProcessor, AutoModelForCausalLM
    model = AutoModelForCausalLM.from_pretrained(
        args.model_path,
        local_files_only=True,
        trust_remote_code=True)
    processor = AutoProcessor.from_pretrained(
        args.model_path,
        local_files_only=True,
        trust_remote_code=True)

    logging.info("Starting image captioner.")
    if args.cronjob == "":
        if sample is None:
            sample = get_input(args.stream)
        return captioning(args, model, processor, sample)

    now = datetime.now(timezone.utc)
    cron = croniter(args.cronjob, now)
    logging.info("Cronjob starting")
    while True:
        n = cron.get_next(datetime).replace(tzinfo=timezone.utc)
        now = datetime.now(timezone.utc)
        next_in_seconds = (n - now).total_seconds()
        if next_in_seconds > 0:
            logging.info(f'Sleeping for {next_in_seconds} seconds')
            time.sleep(next_in_seconds)
        logging.info("Captioning.")
        sample = get_input(args.stream)
        captioning(args, model, processor, sample)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--debug", dest="debug", action="store_true",
        default=False, help="Enable debugging")
    parser.add_argument(
        '--stream', dest='stream',
        action='store', default="file:///app/icon.png", type=str,
        help='URL of the stream or image file. Examples: rtsp://camera:554. Default is file:///app/icon.png.')
    parser.add_argument(
        "--fast-acquisition", dest="fast_acquisition",
        action="store_true", default=False,
        help="Acquire input image before loading the model. This option allows for time-sensitive data acquisition as loading model takes time. Ignored when cronjob mode.")
    parser.add_argument(
        '--out-dir', dest='out_dir',
        action='store', default="", type=str,
        help='Path to save images locally in %%Y-%%m-%%dT%%H:%%M:%%S%z.jpg format')
    parser.add_argument(
        '--cronjob', dest='cronjob',
        action='store', default="", type=str,
        help='Time interval expressed in cronjob style')
    parser.add_argument(
        '--model-path', dest='model_path',
        action='store', default="/app/Florence-2-base", type=str,
        help='Model path. Default is /app/Florence-2-base')
    parser.add_argument(
        '--skip-uploading-image', dest='skip_uploading_image',
        action='store_true', default=False,
        help='When enabled skip uploading the input image. Ignored when --output-dir presents')
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.debug else logging.INFO,
        format='%(asctime)s %(message)s',
        datefmt='%Y/%m/%d %H:%M:%S')
    exit(run(args))