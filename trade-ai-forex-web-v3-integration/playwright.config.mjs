import {defineConfig} from '@playwright/test'
export default defineConfig({
  testDir:'./tests/browser',workers:1,fullyParallel:false,timeout:20000,
  reporter:[['list'],['json',{outputFile:process.env.PWA_TEST_PREVIEW==='1'?'.artifacts/preview-browser-results.json':'.artifacts/browser-results.json'}]],
  use:{baseURL:process.env.PWA_TEST_URL,headless:true,channel:'msedge',
    launchOptions:{args:['--disable-extensions']},screenshot:'only-on-failure',trace:'retain-on-failure'},
})
