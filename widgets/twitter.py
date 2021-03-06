from xml.dom import minidom
from PIL import Image, ImageDraw, ImageOps
from io import BytesIO
import datetime
import urllib

from modules import fetch, fonts, config, helpers, images
from widgets.Widget import Widget
from modules.constants import WIDGET_BOUNDS

TWITTER_BOUNDS = WIDGET_BOUNDS[2]

MAX_LINES = 7
IMAGE_SIZE = 64

# Make an authenticated Twitter API request
def api_request(url):
  headers = {
    'Authorization': f"Bearer {config.get('TWITTER_BEARER_TOKEN')}"
  }
  return fetch.fetch_json(url, headers)

# TwitterWidget class
class TwitterWidget(Widget):
  # Constructor
  def __init__(self):
    super().__init__(TWITTER_BOUNDS)

    self.id = ''
    self.screen_name = ''
    self.name = ''
    self.image = None
    self.image_url = ''
    self.tweet = {
      'text': '',
      'retweet_count': 0,
      'reply_count': 0,
      'like_count': 0,
      'quote_count': 0,
      'display_date': ''
    }

  # Format the user's image to a circle
  def convert_image(self):
    # Create alpha mask for circular crop
    size = (IMAGE_SIZE, IMAGE_SIZE)
    mask = Image.new('L', size, 0)
    draw = ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill=255)

    # Apply the mask
    output = ImageOps.fit(self.image, mask.size, centering=(0.5, 0.5))
    output.putalpha(mask)

    # Flatten alpha to remove outer pixels
    background = Image.new('RGBA', size, (255,255,255))
    alpha_composite = Image.alpha_composite(background, output)
    self.image = alpha_composite

  # Resolve the user ID from the screen name
  def resolve_user_name(self):
    try:
      url = f"https://api.twitter.com/1.1/users/lookup.json?screen_name={config.get('TWITTER_SCREEN_NAME')}"
      json = api_request(url)

      user = json[0]
      self.screen_name = user['screen_name']
      self.name = user['name']
      self.id = user['id_str']
      self.image_url = user['profile_image_url_https'].replace('_normal', '')
    except Exception as err:
      self.set_error(err)

  # Update latest tweet
  def update_data(self):
    try:
      url = f"https://api.twitter.com/2/users/{self.id}/tweets?exclude=replies,retweets&tweet.fields=created_at,public_metrics"
      json = api_request(url)

      self.tweet = json['data'][0]

      # Test 280 length
      # self.tweet['text'] = "This is a small change, but a big move for us. 140 was an arbitrary choice based on the 160 character SMS limit. Proud of how thoughtful the team has been in solving a real problem people have when trying to tweet. And at the same time maintaining our brevity, speed, and essence!"

      # Format datetime
      date_str = self.tweet['created_at'].replace('Z', '')
      date_obj = datetime.datetime.fromisoformat(date_str)
      self.tweet['display_date'] = date_obj.strftime("%H:%M %B %d, %Y")

      # Fetch image (it could change)
      img_data = urllib.request.urlopen(self.image_url).read()
      self.image = Image.open(BytesIO(img_data)).resize((IMAGE_SIZE, IMAGE_SIZE)).convert('RGBA')
      self.convert_image()

      print(f"twitter: {self.tweet}")
      self.unset_error()
    except Exception as err:
      self.set_error(err)

  # Draw the news stories
  def draw(self, image_draw, image):
    if self.error:
      self.draw_error(image_draw)
      return

    try:
      root_y = self.bounds[1] + 5
      line_gap_y = 25

      # Image
      if self.image != None:
        image.paste(self.image, (self.bounds[0], root_y))

      # Screen name, name and date
      content_x = self.bounds[0] + IMAGE_SIZE + 10
      image_draw.text((content_x, root_y + 10), self.name, font = fonts.KEEP_CALM_24, fill = 0)
      image_draw.text((content_x, root_y + 40), f"@{self.screen_name}", font = fonts.KEEP_CALM_20, fill = 0)

      # Tweet content, wrapped
      content = self.tweet['text']
      content_x = self.bounds[0]
      paragraph_y = root_y + 75
      lines = helpers.get_wrapped_lines(content, fonts.KEEP_CALM_20, self.bounds[2])
      font = fonts.KEEP_CALM_18 if len(lines) > MAX_LINES else fonts.KEEP_CALM_20
      lines = helpers.get_wrapped_lines(content, font, self.bounds[2])
      for index, line in enumerate(lines):
        image_draw.text((content_x, paragraph_y + (index * line_gap_y)), line, font = font, fill = 0)

      # Footer, after text
      paragraph_height = helpers.get_paragraph_height(content, font, self.bounds[2], line_gap_y)
      line_y = paragraph_y + paragraph_height + 5
      helpers.draw_divider(image_draw, self.bounds[0], line_y, 390, 1)

      # Tweet stats
      stats_y = line_y + 10
      font = fonts.KEEP_CALM_18
      image.paste(images.ICON_HEART, (self.bounds[0] + 10, stats_y - 3))
      likes_str = helpers.format_number(self.tweet['public_metrics']['like_count'])
      image_draw.text((self.bounds[0] + 40, stats_y), likes_str, font = font, fill = 0)
      image.paste(images.ICON_SPEECH, (self.bounds[0] + 95, stats_y - 1))
      reply_str = helpers.format_number(self.tweet['public_metrics']['reply_count'])
      image_draw.text((self.bounds[0] + 127, stats_y), reply_str, font = font, fill = 0)

      # Tweet date
      date_x = content_x + IMAGE_SIZE + 120
      image_draw.text((date_x, stats_y), f"{self.tweet['display_date']}", font = font, fill = 0)
    except Exception as err:
      self.set_error(err)
      self.draw_error(image_draw)
