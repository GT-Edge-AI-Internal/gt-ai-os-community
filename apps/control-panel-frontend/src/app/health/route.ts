import { NextResponse } from 'next/server';

export async function GET() {
  return NextResponse.json({ 
    status: 'healthy',
    service: 'gt2-control-panel-frontend',
    timestamp: new Date().toISOString()
  });
}