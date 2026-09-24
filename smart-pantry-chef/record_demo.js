const { chromium } = require('playwright');
const path = require('path');
const fs = require('fs');

(async () => {
  const outputDir = path.join(__dirname, 'recordings');
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  console.log('Launching browser...');
  const browser = await chromium.launch({
    headless: true,
    args: ['--no-sandbox', '--disable-setuid-sandbox']
  });

  const context = await browser.newContext({
    viewport: { width: 1280, height: 800 },
    recordVideo: {
      dir: outputDir,
      size: { width: 1280, height: 800 }
    }
  });

  const page = await context.newPage();

  console.log('Navigating to http://localhost:8080...');
  await page.goto('http://localhost:8080');
  await page.waitForTimeout(2500);

  // 1. First prompt: Click first prompt-btn ("What's in my pantry?") - database lookup
  console.log('Action 1: Clicking prompt button "Whats in my pantry?"...');
  const pantryBtn = page.locator('.prompt-btn').first();
  await pantryBtn.click();

  // Wait for agent message response bubble
  console.log('Waiting for pantry database response...');
  await page.waitForSelector('.msg.agent .bubble', { timeout: 25000 });
  await page.waitForTimeout(4000);

  // 2. Second richer prompt: Generate dish image preview
  console.log('Action 2: Typing richer prompt for tool call and image generation...');
  const inputSelector = '#input';
  const promptText = 'Generate a dish photo preview for Garlic Tomato Chicken Pasta';

  for (let i = 0; i < promptText.length; i++) {
    await page.type(inputSelector, promptText[i], { delay: 35 });
  }
  await page.waitForTimeout(600);

  console.log('Submitting second prompt...');
  await page.click('.send-btn');

  // Wait for second agent response
  console.log('Waiting for image generation tool response...');
  await page.waitForFunction(() => {
    const agentBubbles = document.querySelectorAll('.msg.agent .bubble');
    return agentBubbles.length >= 2;
  }, { timeout: 35000 });

  // Additional wait for image element or A2UI image
  await page.waitForTimeout(8000);

  // Demonstrate Copy action bar on second agent bubble
  console.log('Demonstrating Copy action...');
  const secondAgentMsg = page.locator('.msg.agent').nth(1);
  if (await secondAgentMsg.isVisible()) {
    await secondAgentMsg.hover();
    await page.waitForTimeout(1000);
    const copyBtn = secondAgentMsg.locator('.action-btn');
    if (await copyBtn.isVisible()) {
      await copyBtn.click();
      await page.waitForTimeout(2000);
    }
  }

  // Check if an image is rendered and click it for Lightbox
  console.log('Checking for generated image to launch Lightbox modal...');
  const imageElem = page.locator('.msg.agent img, #log img').first();
  if (await imageElem.isVisible()) {
    console.log('Clicking dish image to open Lightbox modal...');
    await imageElem.click();
    await page.waitForTimeout(3500);
    console.log('Closing Lightbox modal with Escape key...');
    await page.keyboard.press('Escape');
    await page.waitForTimeout(2000);
  } else {
    console.log('No img element visible directly in message log.');
  }

  await page.waitForTimeout(3000);

  console.log('Closing context and finalizing recording...');
  await context.close();
  await browser.close();

  // Find recorded video file and rename to demo_recording.webm
  const videoFiles = fs.readdirSync(outputDir).filter(f => f.endsWith('.webm'));
  if (videoFiles.length > 0) {
    const originalVideoPath = path.join(outputDir, videoFiles[0]);
    const finalVideoPath = path.join(outputDir, 'demo_recording.webm');
    if (originalVideoPath !== finalVideoPath) {
      fs.renameSync(originalVideoPath, finalVideoPath);
    }
    const stats = fs.statSync(finalVideoPath);
    console.log(`RECORDING_SUCCESS: ${finalVideoPath} (${stats.size} bytes)`);
  } else {
    console.log('RECORDING_FAILED: No webm file found.');
  }
})();
